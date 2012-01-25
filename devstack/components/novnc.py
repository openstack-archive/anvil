# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

LOG = logging.getLogger("devstack.components.novnc")

#id
TYPE = settings.NOVNC

UTIL_DIR = 'utils'

# FIXME, need to get actual location of nova.API_CONF
APP_OPTIONS = {
    'nova-novncproxy': ['--flagfile-file', sh.joinpths('%ROOT%', "bin", nova.API_CONF), '--web'],
}


class NoVNCUninstaller(comp.PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgUninstallComponent.__init__(self, TYPE, *args, **kargs)


class NoVNCInstaller(comp.PkgInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.git_loc = self.cfg.get("git", "novnc_repo")
        self.git_branch = self.cfg.get("git", "novnc_branch")

    def _get_download_locations(self):
        places = comp.PkgInstallComponent._get_download_locations(self)
        places.append({
            'uri': self.git_loc,
            'branch': self.git_branch,
        })
        return places


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

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)
