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

#id
TYPE = settings.MELANGE_CLIENT
LOG = logging.getLogger("devstack.components.melange_client")

#the pkg json files melange client requires for installation
REQ_PKGS = ['general.json']


class MelangeClientUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)


class MelangeClientInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "melangeclient_repo"),
            'branch': ("git", "melangeclient_branch"),
        })
        return places

    def _get_pkgs(self):
        return list(REQ_PKGS)


class MelangeClientRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, TYPE, *args, **kargs)
