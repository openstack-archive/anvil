# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
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

from anvil import components as comp
from anvil import shell as sh

# Where the application is really
UTIL_DIR = 'utils'

VNC_PROXY_APP = 'nova-novncproxy'


class NoVNCUninstaller(comp.PythonUninstallComponent):
    pass


class NoVNCInstaller(comp.PythonInstallComponent):
    @property
    def python_directories(self):
        # Its python but not one that we need to run setup.py in...
        return {}


class NoVNCRuntime(comp.PythonRuntime):
    @property
    def applications(self):
        path = sh.joinpths(self.get_option('app_dir'), UTIL_DIR, VNC_PROXY_APP)
        argv = ['--config-file', self._get_nova_conf(), '--web', '.']
        return [
            comp.Program(VNC_PROXY_APP, path, argv=argv),
        ]

    def _get_nova_conf(self):
        nova_comp_name = self.get_option('nova-component')
        if nova_comp_name in self.instances:
            # FIXME(harlowja): Have to reach into the nova component to get the config path (puke)
            nova_runtime = self.instances[nova_comp_name]
            return nova_runtime.config_path
        else:
            raise RuntimeError("NoVNC can not be started without the location of the nova configuration file")
