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
from devstack import utils

LOG = logging.getLogger("devstack.components.nova_client")

#id
TYPE = settings.NOVA_CLIENT

#the pkg json files nova client requires for installation
REQ_PKGS = ['general.json', 'nova-client.json']


class NovaClientUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)


class NovaClientInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.git_loc = self.cfg.get("git", "novaclient_repo")
        self.git_branch = self.cfg.get("git", "novaclient_branch")

    def _get_download_locations(self):
        places = comp.PythonInstallComponent._get_download_locations(self)
        places.append({
            'uri': self.git_loc,
            'branch': self.git_branch,
        })
        return places

    def _get_pkgs(self):
        pkgs = comp.PythonInstallComponent._get_pkgs(self)
        for fn in REQ_PKGS:
            full_name = sh.joinpths(settings.STACK_PKG_DIR, fn)
            pkgs = utils.extract_pkg_list([full_name], self.distro, pkgs)
        return pkgs


class NovaClientRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, TYPE, *args, **kargs)


def describe(opts=None):
    description = """
 Module: {module_name}
  Description:
   {description}
  Component options:
   {component_opts}
"""
    params = dict()
    params['component_opts'] = "TBD"
    params['module_name'] = __name__
    params['description'] = __doc__ or "Handles actions for the nova client component."
    out = description.format(**params)
    return out.strip("\n")
