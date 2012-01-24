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

TYPE = settings.KEYSTONE
ROOT_CONF = "keystone.conf"
CONFIGS = [ROOT_CONF]
BIN_DIR = "bin"
CONFIG_DIR = "config"
DB_NAME = "keystone"
CFG_SECTION = 'DEFAULT'
MANAGE_JSON_CONF = 'keystone-manage-cmds.json'
MANAGER_NAME = 'keystone-manage'

#what to start
APP_OPTIONS = {
    'keystone': ['--config-file', sh.joinpths('%ROOT%', "config", ROOT_CONF), "--verbose"],
}

#how we invoke the manage command
KEYSTONE_MNG_CMD = [sh.joinpths("%BIN_DIR%", MANAGER_NAME), '--config-file=%CONFIG_FILE%']


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
        #load the json file which has the keystone setup commands
        cmds_pth = sh.joinpths(settings.STACK_CONFIG_DIR, TYPE, MANAGE_JSON_CONF)
        cmd_map = utils.load_json(cmds_pth)

        #order matters here
        base_cmds = list()

        tenant_cmds = cmd_map.get('tenants', list())
        base_cmds.extend(tenant_cmds)

        user_cmds = cmd_map.get('users', list())
        base_cmds.extend(user_cmds)

        role_cmds = cmd_map.get('roles', list())
        base_cmds.extend(role_cmds)

        token_cmds = cmd_map.get('tokens', list())
        base_cmds.extend(token_cmds)

        service_cmds = cmd_map.get('services', list())
        base_cmds.extend(service_cmds)

        endpoint_cmds = cmd_map.get('endpoints', list())
        base_cmds.extend(endpoint_cmds)

        if(settings.GLANCE in self.instances):
            glance_cmds = cmd_map.get('glance', list())
            base_cmds.extend(glance_cmds)
        if(settings.NOVA in self.instances):
            nova_cmds = cmd_map.get('nova', list())
            base_cmds.extend(nova_cmds)
        if(settings.SWIFT in self.instances):
            swift_cmds = cmd_map.get('swift', list())
            base_cmds.extend(swift_cmds)

        #the above commands are only templates
        #now we fill in the actual application that will run it
        full_cmds = list()
        for cmd in base_cmds:
            if(cmd):
                actual_cmd = KEYSTONE_MNG_CMD + cmd
                full_cmds.append({
                    'cmd': actual_cmd,
                })

        LOG.info("Running (%s) %s commands to setup keystone." % (len(full_cmds), MANAGER_NAME))

        if(len(full_cmds)):
            #execute as templates with replacements coming from the given map
            params = self._get_param_map(MANAGE_JSON_CONF)
            utils.execute_template(*full_cmds, params=params, ignore_missing=True)

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
            mp['DEST'] = self.appdir
            mp['SQL_CONN'] = self.cfg.get_dbdsn(DB_NAME)
        elif(config_fn == MANAGE_JSON_CONF):
            host_ip = self.cfg.get('host', 'ip')
            mp['ADMIN_PASSWORD'] = self.cfg.get('passwords', 'horizon_keystone_admin')
            mp['SERVICE_HOST'] = host_ip
            mp['SERVICE_TOKEN'] = self.cfg.get("passwords", "service_token")
            mp['BIN_DIR'] = self.bindir
            mp['CONFIG_FILE'] = sh.joinpths(self.cfgdir, ROOT_CONF)
            keystone_auth_host = self.cfg.get('keystone', 'keystone_auth_host')
            if(not keystone_auth_host):
                keystone_auth_host = host_ip
            mp['KEYSTONE_AUTH_HOST'] = keystone_auth_host
            mp['KEYSTONE_AUTH_PORT'] = self.cfg.get('keystone', 'keystone_auth_port')
            mp['KEYSTONE_AUTH_PROTOCOL'] = self.cfg.get('keystone', 'keystone_auth_protocol')
            keystone_service_host = self.cfg.get('keystone', 'keystone_service_host')
            if(not keystone_service_host):
                keystone_service_host = host_ip
            mp['KEYSTONE_SERVICE_HOST'] = keystone_service_host
            mp['KEYSTONE_SERVICE_PORT'] = self.cfg.get('keystone', 'keystone_service_port')
            mp['KEYSTONE_SERVICE_PROTOCOL'] = self.cfg.get('keystone', 'keystone_service_protocol')
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
