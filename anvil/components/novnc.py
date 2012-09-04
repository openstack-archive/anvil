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
APP_OPTIONS = {
    # This reaches into the nova configuration file
    # TODO(harlowja) can we stop that?
    VNC_PROXY_APP: ['--config-file', '$NOVA_CONF', '--web', '.'],
}


class NoVNCUninstaller(comp.PythonUninstallComponent):
    pass


class NoVNCInstaller(comp.PythonInstallComponent):
    @property
    def python_directories(self):
        return {}


class NoVNCRuntime(comp.PythonRuntime):
    @property
    def apps_to_start(self):
        apps = []
        for app_name in APP_OPTIONS.keys():
            apps.append({
                'name': app_name,
                'path': sh.joinpths(self.get_option('app_dir'), UTIL_DIR, app_name),
            })
        return apps

    def app_params(self, app_name):
        params = comp.ProgramRuntime.app_params(self, app_name)
        nova_comp_name = self.get_option('nova-component')
        if app_name == VNC_PROXY_APP:
            if nova_comp_name in self.instances:
                # FIXME(harlowja): Have to reach into the nova component to get the config path (puke)
                nova_runtime = self.instances[nova_comp_name]
                params['NOVA_CONF'] = nova_runtime.config_path
            else:
                raise RuntimeError("NoVNC can not be started without the location of the nova configuration file")
        return params

    def app_options(self, app):
        return APP_OPTIONS.get(app)
