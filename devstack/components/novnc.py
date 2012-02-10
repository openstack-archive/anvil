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

from devstack import component as comp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh

from devstack.components import nova

#id
TYPE = settings.NOVNC
LOG = logging.getLogger("devstack.components.novnc")

#where the application is really
UTIL_DIR = 'utils'

VNC_PROXY_APP = 'nova-novncproxy'
APP_OPTIONS = {
    #this reaches into the nova configuration file
    #TODO can we stop that?
    VNC_PROXY_APP: ['--flagfile', '%NOVA_CONF%', '--web', '.'],
}

#the pkg json files novnc requires for installation
REQ_PKGS = ['n-vnc.json']


class NoVNCUninstaller(comp.PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgUninstallComponent.__init__(self, TYPE, *args, **kargs)


class NoVNCInstaller(comp.PkgInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgInstallComponent.__init__(self, TYPE, *args, **kargs)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "novnc_repo"),
            'branch': ("git", "novnc_branch"),
        })
        return places

    def _get_pkgs(self):
        return list(REQ_PKGS)


class NoVNCRuntime(comp.ProgramRuntime):
    def __init__(self, *args, **kargs):
        comp.ProgramRuntime.__init__(self, TYPE, *args, **kargs)

    def _get_apps_to_start(self):
        apps = list()
        for app_name in APP_OPTIONS.keys():
            apps.append({
                'name': app_name,
                'path': sh.joinpths(self.appdir, UTIL_DIR, app_name),
            })
        return apps

    def _get_param_map(self, app_name):
        root_params = comp.ProgramRuntime._get_param_map(self, app_name)
        if app_name == VNC_PROXY_APP and settings.NOVA in self.instances:
            nova_runtime = self.instances.get(settings.NOVA)
            #have to reach into the nova conf (puke)
            root_params['NOVA_CONF'] = sh.joinpths(nova_runtime.cfgdir, nova.API_CONF)
        return root_params

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)
