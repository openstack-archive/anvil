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

#TODO fix these
from Component import (ComponentBase, RuntimeComponent,
                       UninstallComponent, InstallComponent)
import os

LOG = Logger.getLogger("install.nova")
API_CONF = "nova.conf"
CONFIGS = [API_CONF]
DB_NAME = "nova"
#

from Util import (NOVA)
from NovaConf import (NovaConf)

TYPE = NOVA

#what to start
# Does this start nova-compute, nova-volume, nova-network, nova-scheduler
# and optionally nova-wsproxy?
#APP_OPTIONS = {
#    'glance-api': ['--config-file', joinpths('%ROOT%', "etc", API_CONF)],
#    'glance-registry': ['--config-file', joinpths('%ROOT%', "etc", REG_CONF)]
#}


class NovaUninstaller(UninstallComponent):
    def __init__(self, *args, **kargs):
        PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)
        #self.cfgdir = joinpths(self.appdir, CONFIG_ACTUAL_DIR)


class NovaInstaller(InstallComponent):
    def __init__(self, *args, **kargs):
        PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.gitloc = self.cfg.get("git", "nova_repo")
        self.brch = self.cfg.get("git", "nova_branch")
        #self.cfgdir = joinpths(self.appdir, CONFIG_ACTUAL_DIR)

    def _get_download_location(self):
        #where we get nova from
        return (self.gitloc, self.brch)

    def _get_config_files(self):
        #these are the config files we will be adjusting
        return list(CONFIGS)

    def _config_adjust(self, contents, fn):
        nc = NovaConf(self)
        lines = nc.generate()
        return os.linesep.join(lines)

    def _get_param_map(self, fn=None):
        # Not used. NovaConf will be used to generate the config file
        mp = dict()
        return mp


class NovaRuntime(RuntimeComponent):
    def __init__(self, *args, **kargs):
        pass
