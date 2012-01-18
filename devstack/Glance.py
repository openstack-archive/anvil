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
                       PythonRuntime)
from Util import (GLANCE,
                  get_host_ip, param_replace)
from Shell import (deldir, mkdirslist, unlink,
                   joinpths, touch_file)
import Db

LOG = Logger.getLogger("install.glance")

#naming + config files
TYPE = GLANCE
API_CONF = "glance-api.conf"
REG_CONF = "glance-registry.conf"
CONFIGS = [API_CONF, REG_CONF]
DB_NAME = "glance"

#what to start
APP_OPTIONS = {
    'glance-api': ['--config-file', joinpths('%ROOT%', "etc", API_CONF)],
    'glance-registry': ['--config-file', joinpths('%ROOT%', "etc", REG_CONF)]
}
CONFIG_ACTUAL_DIR = 'etc'


class GlanceUninstaller(PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = joinpths(self.appdir, CONFIG_ACTUAL_DIR)


class GlanceRuntime(PythonRuntime):
    def __init__(self, *args, **kargs):
        PythonRuntime.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = joinpths(self.appdir, CONFIG_ACTUAL_DIR)

    def _get_apps_to_start(self):
        return sorted(APP_OPTIONS.keys())

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)


class GlanceInstaller(PythonInstallComponent):
    def __init__(self, *args, **kargs):
        PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.gitloc = self.cfg.get("git", "glance_repo")
        self.brch = self.cfg.get("git", "glance_branch")
        self.cfgdir = joinpths(self.appdir, CONFIG_ACTUAL_DIR)

    def _get_download_location(self):
        #where we get glance from
        return (self.gitloc, self.brch)

    def _get_config_files(self):
        #these are the config files we will be adjusting
        return list(CONFIGS)

    def install(self):
        parent_res = PythonInstallComponent.install(self)
        #setup the database
        self._setup_db()
        return parent_res

    def _setup_db(self):
        Db.drop_db(self.cfg, DB_NAME)
        Db.create_db(self.cfg, DB_NAME)

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
        mp['SQL_CONN'] = self.cfg.get_dbdsn(DB_NAME)
        hostip = get_host_ip(self.cfg)
        mp['SERVICE_HOST'] = hostip
        mp['HOST_IP'] = hostip
        return mp
