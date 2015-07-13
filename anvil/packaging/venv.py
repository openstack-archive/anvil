# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2014 Yahoo! Inc. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import contextlib
import functools
import itertools
import os
import re
import tarfile

import six

from anvil import async
from anvil import colorizer
from anvil import env
from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.packaging import base
from anvil.packaging.helpers import pip_helper

LOG = logging.getLogger(__name__)


def _on_finish(what, time_taken):
    LOG.info("%s took %s seconds", what, time_taken)


# TODO(harlowja): think we can remove this...
class VenvInstallHelper(base.InstallHelper):
    def pre_install(self, pkg, params=None):
        pass

    def post_install(self, pkg, params=None):
        pass


class VenvDependencyHandler(base.DependencyHandler):
    PREREQUISITE_PKGS = frozenset(['pbr'])
    PREREQUISITE_UPGRADE_PKGS = frozenset(['pip'])

    # Sometimes pip fails downloading things, retry it when
    # this happens...
    _RETRIES = 3
    _RETRY_DELAY = 5

    def __init__(self, distro, root_dir,
                 instances, opts, group, prior_groups):
        super(VenvDependencyHandler, self).__init__(distro, root_dir,
                                                    instances, opts, group,
                                                    prior_groups)
        self.cache_dir = sh.joinpths(self.root_dir, "pip-cache")
        self.jobs = max(0, int(opts.get('jobs', 0)))

    def _venv_directory_for(self, instance):
        return sh.joinpths(instance.get_option('component_dir'), 'venv')

    def _install_into_venv(self, instance, requirements, upgrade=False):
        venv_dir = self._venv_directory_for(instance)
        base_pip = [sh.joinpths(venv_dir, 'bin', 'pip')]
        env_overrides = {
            'PATH': os.pathsep.join([sh.joinpths(venv_dir, "bin"),
                                     env.get_key('PATH', default_value='')]),
            'VIRTUAL_ENV': venv_dir,
        }
        sh.mkdirslist(self.cache_dir, tracewriter=self.tracewriter)
        cmd = list(base_pip) + ['install']
        if upgrade:
            cmd.append("--upgrade")
        cmd.extend([
            '--download-cache',
            self.cache_dir,
        ])
        if isinstance(requirements, six.string_types):
            cmd.extend([
                '--requirement',
                requirements
            ])
        else:
            for req in requirements:
                cmd.append(str(req))
        sh.execute(cmd, env_overrides=env_overrides)

    def _is_buildable(self, instance):
        app_dir = instance.get_option('app_dir')
        if app_dir and sh.isdir(app_dir) and hasattr(instance, 'egg_info'):
            return True
        return False

    def _replace_deployment_paths(self, root_dir, replacer):
        total_replacements = 0
        files_replaced = 0
        for path in sh.listdir(root_dir, recursive=True, files_only=True):
            new_contents, replacements = replacer(sh.load_file(path))
            if replacements:
                sh.write_file(path, new_contents)
                total_replacements += replacements
                files_replaced += 1
        return (files_replaced, total_replacements)

    def _make_tarball(self, venv_dir, tar_filename, tar_path):
        with contextlib.closing(tarfile.open(tar_filename, "w:gz")) as tfh:
            for path in sh.listdir(venv_dir, recursive=True):
                tarpath = tar_path + path[len(venv_dir):]
                tarpath = os.path.abspath(tarpath)
                tfh.add(path, recursive=False, arcname=tarpath)

    def package_finish(self):
        super(VenvDependencyHandler, self).package_finish()
        for instance in self.instances:
            if not self._is_buildable(instance):
                continue
            venv_dir = sh.abspth(self._venv_directory_for(instance))

            release = str(instance.get_option("release", default_value=1))
            if release and not release.startswith('-'):
                release = '-' + release
            version_full = instance.egg_info['version'] + release

            # Replace paths with virtualenv deployment directory.
            if self.opts.get('venv_deploy_dir'):
                deploy_dir = sh.joinpths(self.opts.get('venv_deploy_dir'),
                                         instance.name)
                replacer = functools.partial(
                    re.subn, re.escape(instance.get_option('component_dir')),
                    deploy_dir)
                bin_dir = sh.joinpths(venv_dir, 'bin')
                adjustments, files_replaced = self._replace_deployment_paths(bin_dir,
                                                                             replacer)
                if files_replaced:
                    LOG.info("Adjusted %s deployment path(s) in %s files",
                             adjustments, files_replaced)

                tar_path = sh.joinpths(self.opts.get('venv_deploy_dir'), '%s-%s-venv' % (
                                       instance.name, version_full))
            else:
                tar_path = '%s-%s-venv' % (instance.name, version_full)

            # Create a tarball containing the virtualenv.
            tar_filename = sh.joinpths(venv_dir, '%s-%s-venv.tar.gz' % (instance.name,
                                       version_full))
            LOG.info("Making tarball of %s built for %s with version %s at %s", venv_dir,
                     instance.name, version_full, tar_filename)
            utils.time_it(functools.partial(_on_finish, "Tarball creation"),
                          self._make_tarball, venv_dir, tar_filename, tar_path)

    def package_start(self):
        super(VenvDependencyHandler, self).package_start()
        base_cmd = env.get_key('VENV_CMD', default_value='virtualenv')
        for instance in self.instances:
            if not self._is_buildable(instance):
                continue
            # Create a virtualenv...
            venv_dir = self._venv_directory_for(instance)
            sh.mkdirslist(venv_dir, tracewriter=self.tracewriter)
            cmd = [base_cmd, '--clear', venv_dir]
            LOG.info("Creating virtualenv at %s", colorizer.quote(venv_dir))
            sh.execute(cmd)
            self._install_into_venv(instance, self.PREREQUISITE_PKGS)
            self._install_into_venv(instance,
                                    self.PREREQUISITE_UPGRADE_PKGS,
                                    upgrade=True)

    def package_instances(self, instances):
        if not instances:
            return []
        LOG.info("Packaging %s instances using %s threads",
                 len(instances), self.jobs)
        results = [None] * len(instances)
        if self.jobs >= 1:
            executor = async.ChainedWorkerExecutor(self.jobs)
            retryable_exceptions = [
                excp.ProcessExecutionError,
            ]
            run_funcs = []
            for instance in instances:
                func = functools.partial(utils.retry,
                                         self._RETRIES, self._RETRY_DELAY,
                                         self._package_instance, instance,
                                         retryable_exceptions=retryable_exceptions)
                run_funcs.append(func)
            futs = executor.run(run_funcs)
            executor.wait()
            for fut in futs:
                if fut.cancelled():
                    continue
                if fut.done():
                    fut.result()
        else:
            for instance in instances:
                self.package_instance(instance)
        return results

    def _package_instance(self, instance, attempt):
        if not self._is_buildable(instance):
            # Skip things that aren't python...
            LOG.warn("Skipping building %s (not python)",
                     colorizer.quote(instance.name, quote_color='red'))
            return

        def gather_extras():
            extra_reqs = []
            for p in instance.get_option("pips", default_value=[]):
                req = pip_helper.create_requirement(p['name'], p.get('version'))
                extra_reqs.append(req)
            if instance.get_bool_option('use_tests_requires', default_value=True):
                for p in instance.get_option("test_requires", default_value=[]):
                    extra_reqs.append(pip_helper.create_requirement(p))
            return extra_reqs

        all_requires_what = self._filter_download_requires()
        LOG.info("Packaging %s (attempt %s)",
                 colorizer.quote(instance.name), attempt)
        all_requires_mapping = {}
        for req in all_requires_what:
            if isinstance(req, six.string_types):
                req = pip_helper.extract_requirement(req)
            all_requires_mapping[req.key] = req
        direct_requires_what = []
        direct_requires_keys = set()
        egg_info = getattr(instance, 'egg_info', None)
        if egg_info is not None:
            # Ensure we have gotten all the things...
            test_dependencies = (egg_info.get('test_dependencies', [])
                                 if instance.get_bool_option(
                                 'use_tests_requires', default_value=True)
                                 else [])
            for req in itertools.chain(egg_info.get('dependencies', []),
                                       test_dependencies):
                if isinstance(req, six.string_types):
                    req = pip_helper.extract_requirement(req)
                if req.key not in direct_requires_keys:
                    direct_requires_what.append(req)
                    direct_requires_keys.add(req.key)
        requires_what = []
        extra_requires_what = gather_extras()
        for req in extra_requires_what:
            if req.key in all_requires_mapping:
                req = all_requires_mapping[req.key]
            requires_what.append(req)
            try:
                direct_requires_keys.remove(req.key)
            except KeyError:
                pass
        for req in direct_requires_what:
            if req.key not in direct_requires_keys:
                continue
            if req.key in all_requires_mapping:
                req = all_requires_mapping[req.key]
            requires_what.append(req)
        what = 'installation for %s' % colorizer.quote(instance.name)
        utils.time_it(functools.partial(_on_finish, "Dependency %s" % what),
                      self._install_into_venv, instance,
                      requires_what)
        utils.time_it(functools.partial(_on_finish, "Instance %s" % what),
                      self._install_into_venv, instance,
                      [instance.get_option('app_dir')])

    def download_dependencies(self):
        pass
