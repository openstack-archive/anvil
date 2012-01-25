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

import io

from devstack import cfg
from devstack import component as comp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils
from devstack.components import db

LOG = logging.getLogger("devstack.components.keystone")

#id
TYPE = settings.KEYSTONE

#this db will be dropped then created
DB_NAME = "keystone"

#subdirs of the git checkout
BIN_DIR = "bin"
CONFIG_DIR = "etc"

#simple confs
ROOT_CONF = "keystone.conf"
CONFIGS = [ROOT_CONF]
CFG_SECTION = 'DEFAULT'

#this is a special conf
MANAGE_DATA_CONF = 'keystone_data.sh'
MANAGER_CMD_ROOT = [sh.joinpths("/", "bin", 'bash')]

#what to start
APP_OPTIONS = {
    'keystone': ['-c', sh.joinpths('%ROOT%', CONFIG_DIR, ROOT_CONF),
                "--verbose", '-d',
                '--log-config=' + sh.joinpths('%ROOT%', CONFIG_DIR, 'logging.cnf')]
}


class KeystoneUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)


class KeystoneInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.git_loc = self.cfg.get("git", "keystone_repo")
        self.git_branch = self.cfg.get("git", "keystone_branch")
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)

    def _get_download_locations(self):
        places = comp.PythonInstallComponent._get_download_locations(self)
        places.append({
            'uri': self.git_loc,
            'branch': self.git_branch,
        })
        return places

    def post_install(self):
        parent_result = comp.PythonInstallComponent.post_install(self)
        self._setup_db()
        self._setup_data()
        return parent_result

    def _get_config_files(self):
        return list(CONFIGS)

    def _setup_db(self):
        db.drop_db(self.cfg, DB_NAME)
        db.create_db(self.cfg, DB_NAME)

    def _setup_data(self):
        # TODO clean this up once it works
        src_fn = sh.joinpths(settings.STACK_CONFIG_DIR, TYPE, MANAGE_DATA_CONF)
        contents = sh.load_file(src_fn)
        params = self._get_param_map(MANAGE_DATA_CONF)
        contents = utils.param_replace(contents, params, True)
        tgt_fn = sh.joinpths(self.bindir, MANAGE_DATA_CONF)
        sh.write_file(tgt_fn, contents)
        # This environment additions are important
        # in that they eventually affect how keystone-manage runs so make sure its set.
        env = dict()
        env['ENABLED_SERVICES'] = ",".join(self.instances.keys())
        env['BIN_DIR'] = self.bindir
        setup_cmd = MANAGER_CMD_ROOT + [tgt_fn]
        LOG.info("Running (%s) command to setup keystone." % (" ".join(setup_cmd)))
        sh.execute(*setup_cmd, env_overrides=env)

    def _config_adjust(self, contents, name):
        if(name not in CONFIGS):
            return contents
        #use config parser and
        #then extract known configs that
        #will need locations/directories/files made (or touched)...
        with io.BytesIO(contents) as stream:
            config = cfg.IgnoreMissingConfigParser()
            config.readfp(stream)
            log_filename = config.get('log_file', CFG_SECTION)
            if(log_filename):
                LOG.info("Ensuring log file %s exists and is empty" % (log_filename))
                log_dir = sh.dirname(log_filename)
                if(log_dir):
                    LOG.info("Ensuring log directory %s exists" % (log_dir))
                    self.tracewriter.make_dir(log_dir)
                #destroy then recreate it (the log file)
                sh.unlink(log_filename)
                sh.touch_file(log_filename)
                self.tracewriter.file_touched(log_filename)
            #we might need to handle more in the future...
        #nothing modified so just return the original
        return contents

    def _get_param_map(self, config_fn):
        #these be used to fill in the configuration/cmds +
        #params with actual values
        mp = dict()
        if(config_fn == ROOT_CONF):
            host_ip = self.cfg.get('host', 'ip')
            mp['DEST'] = self.appdir
            mp['SQL_CONN'] = self.cfg.get_dbdsn(DB_NAME)
            mp['SERVICE_HOST'] = host_ip
            mp['ADMIN_HOST'] = host_ip
        elif(config_fn == MANAGE_DATA_CONF):
            host_ip = self.cfg.get('host', 'ip')
            mp['ADMIN_PASSWORD'] = self.cfg.get('passwords', 'horizon_keystone_admin')
            mp['SERVICE_HOST'] = host_ip
            mp.update(get_shared_params(self.cfg))
        else:
            mp['DEST'] = self.appdir
            mp['BIN_DIR'] = self.bindir
            mp['CONFIG_FILE'] = sh.joinpths(self.cfgdir, ROOT_CONF)
        return mp


class KeystoneRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)

    def _get_apps_to_start(self):
        apps = list()
        for app_name in APP_OPTIONS.keys():
            apps.append({
                'name': app_name,
                'path': sh.joinpths(self.bindir, app_name),
            })
        return apps

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)


def get_shared_params(cfg):
    mp = dict()
    host_ip = cfg.get('host', 'ip')
    keystone_auth_host = cfg.get('keystone', 'keystone_auth_host')
    if(not keystone_auth_host):
        keystone_auth_host = host_ip
    mp['KEYSTONE_AUTH_HOST'] = keystone_auth_host
    mp['KEYSTONE_AUTH_PORT'] = cfg.get('keystone', 'keystone_auth_port')
    mp['KEYSTONE_AUTH_PROTOCOL'] = cfg.get('keystone', 'keystone_auth_protocol')
    keystone_service_host = cfg.get('keystone', 'keystone_service_host')
    if(not keystone_service_host):
        keystone_service_host = host_ip
    mp['KEYSTONE_SERVICE_HOST'] = keystone_service_host
    mp['KEYSTONE_SERVICE_PORT'] = cfg.get('keystone', 'keystone_service_port')
    mp['KEYSTONE_SERVICE_PROTOCOL'] = cfg.get('keystone', 'keystone_service_protocol')
    mp['SERVICE_TOKEN'] = cfg.get("passwords", "service_token")
    return mp
