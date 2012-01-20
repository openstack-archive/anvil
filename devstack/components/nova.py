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
from devstack import constants
from devstack import log as logging
from devstack import shell as sh
from devstack import utils
from devstack.components import nova_conf as nc

LOG = logging.getLogger("devstack.components.nova")
API_CONF = "nova.conf"
CONFIGS = [API_CONF]
DB_NAME = "nova"
TYPE = constants.NOVA

#what to start
# Does this start nova-compute, nova-volume, nova-network, nova-scheduler
# and optionally nova-wsproxy?
#APP_OPTIONS = {
#    'glance-api': ['--config-file', joinpths('%ROOT%', "etc", API_CONF)],
#    'glance-registry': ['--config-file', joinpths('%ROOT%', "etc", REG_CONF)]
#}


class NovaUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)
        #self.cfgdir = joinpths(self.appdir, CONFIG_ACTUAL_DIR)


class NovaInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.gitloc = self.cfg.get("git", "nova_repo")
        self.brch = self.cfg.get("git", "nova_branch")
        # TBD is this the install location of the conf file?
        #self.cfgdir = joinpths(self.appdir, CONFIG_ACTUAL_DIR)

    def _get_download_location(self):
        places = comp.PythonInstallComponent._get_download_locations(self)
        places.append({
            'uri': self.gitloc,
            'branch': self.brch,
        })
        return places

    def configure(self):
        # FIXME, is this necessary? Is it for the template source?
        dirsmade = sh.mkdirslist(self.cfgdir)
        self.tracewriter.dir_made(*dirsmade)
        nconf = nc.NovaConf(self)
        LOG.info("Getting dynamic content for nova.conf")
        # Get dynamic content for nova.conf
        lines = nconf.generate()
        LOG.debug("Got conf lines, %s" % (lines))
        # Set up and write lines to the file
        fn = API_CONF
        tgtfn = self._get_full_config_name(fn)
        dirsmade = sh.mkdirslist(os.path.dirname(tgtfn))
        self.tracewriter.dir_made(*dirsmade)
        LOG.info("Writing configuration file %s" % (tgtfn))
        #this trace is used to remove the files configured
        sh.write_file(tgtfn, os.linesep.join(lines))
        self.tracewriter.cfg_write(tgtfn)
        return 1


class NovaRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, TYPE, *args, **kargs)
