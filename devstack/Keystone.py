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

import os
import os.path

import Util
from Util import (KEYSTONE, get_pkg_list, get_dbdsn,
                  param_replace)
import Logger
import Component
import Downloader
import Trace
from Trace import (TraceWriter, TraceReader)
import Shell
from Shell import (execute, mkdirslist, write_file,
                    load_file, joinpths, touch_file,
                    unlink)

LOG = Logger.getLogger("install.keystone")
TYPE = KEYSTONE
PY_INSTALL = ['python', 'setup.py', 'develop']
ROOT_CONF = "keystone.conf"
CONFIGS = [ROOT_CONF]
BIN_DIR = "bin"
DATA_SCRIPT = "keystone_data.sh"
DB_NAME = "keystone"


class KeystoneBase(Component.ComponentBase):
    def __init__(self, *args, **kargs):
        Component.ComponentBase.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = joinpths(self.appdir, Util.CONFIG_DIR)
        self.bindir = joinpths(self.appdir, BIN_DIR)


class KeystoneUninstaller(KeystoneBase, Component.UninstallComponent):
    def __init__(self, *args, **kargs):
        KeystoneBase.__init__(self, *args, **kargs)


class KeystoneInstaller(KeystoneBase, Component.InstallComponent):
    def __init__(self, *args, **kargs):
        KeystoneBase.__init__(self, *args, **kargs)
        self.gitloc = self.cfg.get("git", "keystone_repo")
        self.brch = self.cfg.get("git", "keystone_branch")
        self.tracewriter = TraceWriter(self.tracedir, Trace.IN_TRACE)

    def download(self):
        dirsmade = Downloader.download(self.appdir, self.gitloc, self.brch)
        # This trace isn't used yet but could be
        self.tracewriter.downloaded(self.appdir, self.gitloc)
        # This trace is used to remove the dirs created
        self.tracewriter.dir_made(*dirsmade)
        return self.tracedir

    def install(self):
        pkgs = get_pkg_list(self.distro, TYPE)
        pkgnames = pkgs.keys()
        pkgnames.sort()
        LOG.debug("Installing packages %s" % (", ".join(pkgnames)))
        self.packager.install_batch(pkgs)
        for name in pkgnames:
            packageinfo = pkgs.get(name)
            version = packageinfo.get("version", "")
            remove = packageinfo.get("removable", True)
            # This trace is used to remove the pkgs
            self.tracewriter.package_install(name, remove, version)
        dirsmade = mkdirslist(self.tracedir)
        # This trace is used to remove the dirs created
        self.tracewriter.dir_made(*dirsmade)
        recordwhere = Trace.touch_trace(self.tracedir, Trace.PY_TRACE)
        # This trace is used to remove the trace created
        self.tracewriter.py_install(recordwhere)
        (sysout, stderr) = execute(*PY_INSTALL, cwd=self.appdir, run_as_root=True)
        write_file(recordwhere, sysout)
        #adjust db
        self._setup_db()
        #setup any data
        self._setup_data()
        return self.tracedir

    def configure(self):
        dirsmade = mkdirslist(self.cfgdir)
        self.tracewriter.dir_made(*dirsmade)
        for fn in CONFIGS:
            sourcefn = joinpths(Util.STACK_CONFIG_DIR, TYPE, fn)
            tgtfn = joinpths(self.cfgdir, fn)
            LOG.info("Configuring template file %s" % (sourcefn))
            contents = load_file(sourcefn)
            pmap = self._get_param_map(fn)
            LOG.info("Replacing parameters in file %s" % (sourcefn))
            LOG.debug("Replacements = %s" % (pmap))
            contents = param_replace(contents, pmap)
            LOG.debug("Applying side-effects of param replacement for template %s" % (sourcefn))
            self._config_apply(contents, fn)
            LOG.info("Writing configuration file %s" % (tgtfn))
            write_file(tgtfn, contents)
            # This trace is used to remove the files configured
            self.tracewriter.cfg_write(tgtfn)
        return self.tracedir

    def _setup_db(self):
        pass

    def _setup_data(self):
        pass

    def _config_apply(self, contents, fn):
        lines = contents.splitlines()
        for line in lines:
            cleaned = line.strip()
            if(len(cleaned) == 0 or cleaned[0] == '#' or cleaned[0] == '['):
                #not useful to examine these
                continue
            pieces = cleaned.split("=", 1)
            if(len(pieces) != 2):
                continue
            key = pieces[0].strip()
            val = pieces[1].strip()
            if(len(key) == 0 or len(val) == 0):
                continue
            #now we take special actions
            if(key == 'log_file'):
                # Ensure that we can write to the log file
                dirname = os.path.dirname(val)
                if(len(dirname)):
                    dirsmade = mkdirslist(dirname)
                    # This trace is used to remove the dirs created
                    self.tracewriter.dir_made(*dirsmade)
                # Destroy then recreate it
                unlink(val)
                touch_file(val)
                self.tracewriter.file_touched(val)

    def _get_param_map(self, fn):
        # These be used to fill in the configuration
        # params with actual values
        mp = dict()
        mp['DEST'] = self.appdir
        mp['SQL_CONN'] = get_dbdsn(self.cfg, DB_NAME)
        return mp


class KeystoneRuntime(KeystoneBase, Component.RuntimeComponent):
    def __init__(self, *args, **kargs):
        KeystoneBase.__init__(self, *args, **kargs)
