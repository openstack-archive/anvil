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
from devstack import constants as co
from devstack import log as logging
from devstack import shell as sh
from devstack.components import nova_conf as nc

LOG = logging.getLogger("devstack.components.nova")

API_CONF = "nova.conf"
PASTE_CONF = 'nova-api-paste.ini'
CONFIGS = [API_CONF]

DB_NAME = "nova"
BIN_DIR = 'bin'
TYPE = co.NOVA


class NovaUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)
        #self.cfgdir = joinpths(self.appdir, CONFIG_ACTUAL_DIR)


class NovaInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.git_repo = self.cfg.get("git", "nova_repo")
        self.git_branch = self.cfg.get("git", "nova_branch")
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)

    def _get_download_locations(self):
        places = comp.PythonInstallComponent._get_download_locations(self)
        places.append({
            'uri': self.git_repo,
            'branch': self.git_branch,
        })
        return places

    def _generate_nova_conf(self):
        LOG.debug("Generating dynamic content for nova configuration")
        dirs = dict()
        dirs['app'] = self.appdir
        dirs['cfg'] = self.cfgdir
        dirs['bin'] = self.bindir
        conf_gen = nc.NovaConfigurator(self.cfg, self.all_components)
        nova_conf = conf_gen.configure(dirs)
        tgtfn = self._get_target_config_name(API_CONF)
        LOG.info("Created nova configuration:")
        LOG.info(nova_conf)
        LOG.debug("Placing it in %s" % (tgtfn))
        sh.write_file(tgtfn, nova_conf)
        #we configured one file, return that we did that
        return 1

    def _configure_files(self):
        return self._generate_nova_conf()


class NovaRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, TYPE, *args, **kargs)
