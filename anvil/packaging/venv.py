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

import itertools
import os
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


# TODO(harlowja): think we can remove this...
class VenvInstallHelper(base.InstallHelper):
    def pre_install(self, pkg, params=None):
        pass

    def post_install(self, pkg, params=None):
        pass


class VenvDependencyHandler(base.DependencyHandler):
    # PBR seems needed everywhere...
    _PREQ_PKGS = frozenset(['pbr'])

    def __init__(self, distro, root_dir, instances, opts):
        super(VenvDependencyHandler, self).__init__(distro, root_dir,
                                                    instances, opts)
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

    def package_finish(self):
        super(VenvDependencyHandler, self).package_finish()
        for instance in self.instances:
            if not self._is_buildable(instance):
                continue
            venv_dir = sh.abspth(self._venv_directory_for(instance))
            tar_filename = sh.joinpths(venv_dir, '%s-venv.tar.gz' % instance.name)
            LOG.info("Making tarball of %s built for %s at", venv_dir,
                     instance.name, tar_filename)
            with tarfile.open(tar_filename, "w:gz") as tfh:
                for path in sh.listdir(venv_dir, recursive=True):
                    tfh.add(path, recursive=False,
                            arcname=path[len(venv_dir):])

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
            requires_what = self._filter_download_requires()
            requires_keys = set()
            for req in requires_what:
                if isinstance(req, six.string_types):
                    req = pip_helper.extract_requirement(req)
                requires_keys.add(req.key)
            egg_info = getattr(instance, 'egg_info', None)
            if egg_info is not None:
                # Ensure we have gotten all the things...
                for req in itertools.chain(egg_info.get('dependencies', []),
                                           egg_info.get('test_dependencies', [])):
                    if isinstance(req, six.string_types):
                        req = pip_helper.extract_requirement(req)
                    if req.key not in requires_keys:
                        requires_what.append(req)
                        requires_keys.add(req.key)
            self._install_into_venv(instance, requires_what)
            self._install_into_venv(instance, [instance.get_option('app_dir')])
        else:
            LOG.warn("Skipping building %s (not python)",
                     colorizer.quote(instance.name, quote_color='red'))

    def download_dependencies(self):
        pass
