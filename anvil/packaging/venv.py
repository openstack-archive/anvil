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

from anvil import colorizer
from anvil import env
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
    # PBR seems needed everywhere...
    _PREQ_PKGS = frozenset(['pbr'])

    def __init__(self, distro, root_dir,
                 instances, opts, group, prior_groups):
        super(VenvDependencyHandler, self).__init__(distro, root_dir,
                                                    instances, opts, group,
                                                    prior_groups)
        self.cache_dir = sh.joinpths(self.root_dir, "pip-cache")

    def _venv_directory_for(self, instance):
        return sh.joinpths(instance.get_option('component_dir'), 'venv')

    def _install_into_venv(self, instance, requirements):
        venv_dir = self._venv_directory_for(instance)
        base_pip = [sh.joinpths(venv_dir, 'bin', 'pip')]
        env_overrides = {
            'PATH': os.pathsep.join([sh.joinpths(venv_dir, "bin"),
                                     env.get_key('PATH', default_value='')]),
            'VIRTUAL_ENV': venv_dir,
        }
        sh.mkdirslist(self.cache_dir, tracewriter=self.tracewriter)

        def try_install(attempt, requirements):
            cmd = list(base_pip) + ['install']
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

        # Sometimes pip fails downloading things, retry it when this happens...
        utils.retry(3, 5, try_install, requirements=requirements)

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

    def package_finish(self):
        super(VenvDependencyHandler, self).package_finish()
        for instance in self.instances:
            if not self._is_buildable(instance):
                continue
            venv_dir = sh.abspth(self._venv_directory_for(instance))

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

            # Create a tarball containing the virtualenv.
            tar_filename = sh.joinpths(venv_dir, '%s-venv.tar.gz' % instance.name)
            LOG.info("Making tarball of %s built for %s at %s", venv_dir,
                     instance.name, tar_filename)
            with contextlib.closing(tarfile.open(tar_filename, "w:gz")) as tfh:
                for path in sh.listdir(venv_dir, recursive=True):
                    tfh.add(path, recursive=False, arcname=path[len(venv_dir):])

    def package_start(self):
        super(VenvDependencyHandler, self).package_start()
        for instance in self.instances:
            if not self._is_buildable(instance):
                continue
            # Create a virtualenv...
            venv_dir = self._venv_directory_for(instance)
            sh.mkdirslist(venv_dir, tracewriter=self.tracewriter)
            cmd = ['virtualenv', '--clear', venv_dir]
            LOG.info("Creating virtualenv at %s", colorizer.quote(venv_dir))
            sh.execute(cmd)
            if self._PREQ_PKGS:
                self._install_into_venv(instance, self._PREQ_PKGS)

    def package_instance(self, instance):
        # Skip things that aren't python...
        if self._is_buildable(instance):
            all_requires_what = self._filter_download_requires()
            all_requires_mp = {}
            for req in all_requires_what:
                if isinstance(req, six.string_types):
                    req = pip_helper.extract_requirement(req)
                all_requires_mp[req.key] = req
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
            for req in direct_requires_what:
                if req.key in all_requires_mp:
                    req = all_requires_mp[req.key]
                requires_what.append(req)
            utils.time_it(functools.partial(_on_finish, "Dependency installation"),
                          self._install_into_venv, instance,
                          requires_what)
            utils.time_it(functools.partial(_on_finish, "Instance installation"),
                          self._install_into_venv, instance,
                          [instance.get_option('app_dir')])
        else:
            LOG.warn("Skipping building %s (not python)",
                     colorizer.quote(instance.name, quote_color='red'))

    def download_dependencies(self):
        pass
