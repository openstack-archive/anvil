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

from anvil import component as comp
from anvil import log as logging
from anvil import shell as sh

from anvil.components import nova

LOG = logging.getLogger(__name__)

# Where the application is really
UTIL_DIR = 'utils'

VNC_PROXY_APP = 'nova-novncproxy'
APP_OPTIONS = {
    # This reaches into the nova configuration file
    # TODO can we stop that?
    VNC_PROXY_APP: ['--flagfile', '%NOVA_CONF%', '--web', '.'],
}


class NoVNCMixin(object):
    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "novnc_repo"),
            'branch': ("git", "novnc_branch"),
        })
        return places


class NoVNCUninstaller(NoVNCMixin, comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)


class NoVNCInstaller(NoVNCMixin, comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)

    def _get_python_directories(self):
        return dict()


class NoVNCRuntime(NoVNCMixin, comp.ProgramRuntime):
    def __init__(self, *args, **kargs):
        comp.ProgramRuntime.__init__(self, *args, **kargs)

    def _get_apps_to_start(self):
        apps = list()
        for app_name in APP_OPTIONS.keys():
            apps.append({
                'name': app_name,
                'path': sh.joinpths(self.get_option('app_dir'), UTIL_DIR, app_name),
            })
        return apps

    def _get_param_map(self, app_name):
        root_params = comp.ProgramRuntime._get_param_map(self, app_name)
        nova_comp = self.get_option('nova-component')
        if nova_comp and app_name == VNC_PROXY_APP and nova_comp in self.instances:
            # FIXME: Have to reach into the nova conf (puke)
            nova_runtime = self.instances[nova_comp]
            root_params['NOVA_CONF'] = sh.joinpths(nova_runtime.get_option('cfg_dir'), nova.API_CONF)
        return root_params

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)
