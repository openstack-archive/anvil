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

import json
import os.path

import Logger
from Component import (PythonUninstallComponent,
                       PythonInstallComponent,
                       ProgramRuntime)
import Shell
import Util
import Runner
from runners.Foreground import (ForegroundRunner)
from Util import (GLANCE,
                  get_host_ip,
                  param_replace, get_dbdsn,
                  )
from Shell import (deldir, mkdirslist, unlink,
                   joinpths, touch_file)
from Exceptions import (StopException, StartException, InstallException)

LOG = Logger.getLogger("install.glance")

#naming + config files
TYPE = GLANCE
API_CONF = "glance-api.conf"
REG_CONF = "glance-registry.conf"
CONFIGS = [API_CONF, REG_CONF]
DB_NAME = "glance"

#what to start
APPS_TO_START = ['glance-api', 'glance-registry']
APP_OPTIONS = {
    'glance-api': ['--config-file', joinpths('%ROOT%', "etc", API_CONF)],
    'glance-registry': ['--config-file', joinpths('%ROOT%', "etc", REG_CONF)]
}
CONFIG_ACTUAL_DIR = 'etc'


class GlanceUninstaller(PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = joinpths(self.appdir, CONFIG_ACTUAL_DIR)

class GlanceRuntime(ProgramRuntime):
    def __init__(self, *args, **kargs):
        ProgramRuntime.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = joinpths(self.appdir, CONFIG_ACTUAL_DIR)

    def _was_installed(self):
        pres = ProgramRuntime._was_installed(self)
        if(pres == False):
            return False
        pylisting = self.tracereader.py_listing()
        if(pylisting and len(pylisting)):
            return True
        return False

    def _get_apps_to_start(self):
        raise list(APPS_TO_START)

    def _get_app_options(self, app, params):
        opts = list()
        if(app in APP_OPTIONS):
            for opt in APP_OPTIONS.get(app):
                opts.append(param_replace(opt, params))
        return opts
        
class GlanceInstaller(PythonInstallComponent):
    def __init__(self, *args, **kargs):
        PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.gitloc = self.cfg.get("git", "glance_repo")
        self.brch = self.cfg.get("git", "glance_branch")
        self.cfgdir = joinpths(self.appdir, CONFIG_ACTUAL_DIR)

    def _get_download_location(self):
        uri = self.gitloc
        branch = self.brch
        return (uri, branch)

    def _get_config_files(self):
        return list(CONFIGS)
        
    def _config_adjust(self, contents, fn):
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
            if(key == 'filesystem_store_datadir'):
                #delete existing images
                deldir(val)
                #recreate the image directory
                dirsmade = mkdirslist(val)
                self.tracewriter.dir_made(*dirsmade)
            elif(key == 'log_file'):
                #ensure that we can write to the log file
                dirname = os.path.dirname(val)
                if(len(dirname)):
                    dirsmade = mkdirslist(dirname)
                    #this trace is used to remove the dirs created
                    self.tracewriter.dir_made(*dirsmade)
                #destroy then recreate it (the log file)
                unlink(val)
                touch_file(val)
                self.tracewriter.file_touched(val)
            elif(key == 'image_cache_datadir'):
                #destroy then recreate the image cache directory
                deldir(val)
                dirsmade = mkdirslist(val)
                #this trace is used to remove the dirs created
                self.tracewriter.dir_made(*dirsmade)
            elif(key == 'scrubber_datadir'):
                #destroy then recreate the scrubber data directory
                deldir(val)
                dirsmade = mkdirslist(val)
                #this trace is used to remove the dirs created
                self.tracewriter.dir_made(*dirsmade)
        return contents

    def _get_param_map(self, fn=None):
        #this dict will be used to fill in the configuration
        #params with actual values
        mp = dict()
        mp['DEST'] = self.appdir
        mp['SYSLOG'] = self.cfg.getboolean("default", "syslog")
        mp['SERVICE_TOKEN'] = self.cfg.getpw("passwords", "service_token")
        mp['SQL_CONN'] = get_dbdsn(self.cfg, DB_NAME)
        hostip = get_host_ip(self.cfg)
        mp['SERVICE_HOST'] = hostip
        mp['HOST_IP'] = hostip
        return mp
