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

from anvil import colorizer
from anvil import log as logging
from anvil.packaging import base
from anvil import shell as sh
from anvil import utils

LOG = logging.getLogger(__name__)


# TODO(harlowja): think we can remove this...
class VenvInstallHelper(base.InstallHelper):
    def pre_install(self, pkg, params=None):
        pass

    def post_install(self, pkg, params=None):
        pass


class VenvDependencyHandler(base.DependencyHandler):
    def __init__(self, distro, root_dir, instances, opts):
        super(VenvDependencyHandler, self).__init__(distro, root_dir,
                                                    instances, opts)

    def _venv_directory_for(self, instance):
        return sh.joinpths(instance.get_option('component_dir'), 'venv')

    def _install_into_venv(self, instance, requirements):
        venv_dir = self._venv_directory_for(instance)
        base_pip = [sh.joinpths(venv_dir, 'bin', 'pip')]

        def try_install(attempt, requirements):
            cmd = list(base_pip) + ['install']
            for req in requirements:
                cmd.append(str(req))
            sh.execute(cmd)

        utils.retry(3, 5, try_install, requirements=requirements)

    def package_start(self):
        super(VenvDependencyHandler, self).package_start()
        for instance in self.instances:
            # Create a virtualenv...
            venv_dir = self._venv_directory_for(instance)
            sh.mkdirslist(venv_dir, tracewriter=self.tracewriter)
            cmd = ['virtualenv', '--clear', venv_dir]
            LOG.info("Creating virtualenv at %s", colorizer.quote(venv_dir))
            sh.execute(cmd)
            # PBR seems needed everywhere...
            self._install_into_venv(instance, ['pbr'])

    def package_instance(self, instance):
        self._install_into_venv(instance, self._filter_download_requires())
        self._install_into_venv(instance, [instance.get_option('app_dir')])

    def download_dependencies(self):
        pass
