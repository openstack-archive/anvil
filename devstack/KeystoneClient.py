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


LOG = Logger.getLogger("install.keystone.client")
TYPE = Util.KEYSTONE_CLIENT


class KeyStoneClientUninstaller(PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)


class KeyStoneClientInstaller(PythonInstallComponent):
    def __init__(self, *args, **kargs):
        PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.gitloc = self.cfg.get("git", "keystoneclient_repo")
        self.brch = self.cfg.get("git", "keystoneclient_branch")

    def _get_download_locations(self):
        places = PythonInstallComponent._get_download_locations(self)
        places.append({
            'uri': self.gitloc,
            'branch': self.brch,
        })
        return places


class KeyStoneClientRuntime(NullRuntime):
    def __init__(self, *args, **kargs):
        NullRuntime.__init__(self, TYPE, *args, **kargs)
