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


import Logger
import Util

#TODO fix these
from Component import (PythonUninstallComponent,
                        PythonInstallComponent,
                        NullRuntime)


LOG = Logger.getLogger("install.openstackx")
TYPE = Util.OPENSTACK_X


class OpenstackXUninstaller(PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)


class OpenstackXInstaller(PythonInstallComponent):
    def __init__(self, *args, **kargs):
        PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.git_loc = self.cfg.get("git", "openstackx_repo")
        self.git_branch = self.cfg.get("git", "openstackx_branch")

    def _get_download_locations(self):
        places = PythonInstallComponent._get_download_locations(self)
        places.append({
            'uri': self.git_loc,
            'branch': self.git_branch,
        })
        return places


class OpenstackXRuntime(NullRuntime):
    def __init__(self, *args, **kargs):
        NullRuntime.__init__(self, TYPE, *args, **kargs)
