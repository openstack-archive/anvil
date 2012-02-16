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

import io

from devstack import cfg
from devstack import component as comp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

from devstack.components import db

#id
TYPE = settings.KEYSTONE
LOG = logging.getLogger("devstack.components.keystone")

#this db will be dropped then created
DB_NAME = "keystone"

#subdirs of the git checkout
BIN_DIR = "bin"
CONFIG_DIR = "etc"

#simple confs
ROOT_CONF = "keystone.conf"
CATALOG_CONF = 'default_catalog.templates'
CONFIGS = [ROOT_CONF, CATALOG_CONF]
CFG_SECTION = 'DEFAULT'

#this is a special conf
MANAGE_DATA_CONF = 'keystone_data.sh'
MANAGER_CMD_ROOT = [sh.joinpths("/", "bin", 'bash')]

#sync db command
SYNC_DB_CMD = [sh.joinpths('%BINDIR%', 'keystone-manage'), 'sync_database']

#what to start
APP_OPTIONS = {
    'keystone': ['--config-file', sh.joinpths('%ROOT%', CONFIG_DIR, ROOT_CONF),
                "--verbose", '-d',
                '--log-config=' + sh.joinpths('%ROOT%', CONFIG_DIR, 'logging.cnf')]
}

#the pkg json files keystone requires for installation
REQ_PKGS = ['general.json', 'keystone.json']

#pip files that keystone requires
REQ_PIPS = ['general.json', 'keystone.json']


class KeystoneUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)


class KeystoneInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "keystone_repo"),
            'branch': ("git", "keystone_branch"),
        })
        return places

    def _get_pips(self):
        return list(REQ_PIPS)

    def _get_pkgs(self):
        return list(REQ_PKGS)

    def _get_symlinks(self):
        links = dict()
        for fn in self._get_config_files():
            source_fn = self._get_target_config_name(fn)
            links[source_fn] = sh.joinpths("/", "etc", "keystone", fn)
        return links

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        self._setup_db()
        self._sync_db()
        self._setup_data()

    def _sync_db(self):
        LOG.info("Syncing keystone to database named %s.", DB_NAME)
        params = dict()
        #it seems like this command only works if fully specified
        #probably a bug
        params['BINDIR'] = self.bindir
        cmds = [{'cmd': SYNC_DB_CMD}]
        utils.execute_template(*cmds, cwd=self.bindir, params=params)

    def _get_config_files(self):
        return list(CONFIGS)

    def _setup_db(self):
        LOG.info("Fixing up database named %s.", DB_NAME)
        db.drop_db(self.cfg, DB_NAME)
        db.create_db(self.cfg, DB_NAME)

    def _setup_data(self):
        LOG.info("Configuring data setup template %s.", MANAGE_DATA_CONF)
        #first write it
        (_, contents) = utils.load_template(self.component_name, MANAGE_DATA_CONF)
        params = self._get_param_map(MANAGE_DATA_CONF)
        contents = utils.param_replace(contents, params, True)
        tgt_fn = sh.joinpths(self.bindir, MANAGE_DATA_CONF)
        sh.write_file(tgt_fn, contents)
        sh.chmod(tgt_fn, 0755)
        #now run it
        #these environment additions are important
        #in that they eventually affect how this script runs
        env = dict()
        env['ENABLED_SERVICES'] = ",".join(self.instances.keys())
        env['BIN_DIR'] = self.bindir
        setup_cmd = MANAGER_CMD_ROOT + [tgt_fn]
        LOG.info("Running (%s) command to setup keystone." % (" ".join(setup_cmd)))
        sh.execute(*setup_cmd, env_overrides=env)

    def _config_adjust(self, contents, name):
        if name not in CONFIGS:
            return contents
        #use config parser and
        #then extract known configs that
        #will need locations/directories/files made (or touched)...
        with io.BytesIO(contents) as stream:
            config = cfg.IgnoreMissingConfigParser()
            config.readfp(stream)
            log_filename = config.get('log_file', CFG_SECTION)
            if log_filename:
                LOG.info("Ensuring log file %s exists and is empty." % (log_filename))
                log_dir = sh.dirname(log_filename)
                if log_dir:
                    LOG.info("Ensuring log directory %s exists." % (log_dir))
                    self.tracewriter.make_dir(log_dir)
                #destroy then recreate it (the log file)
                sh.unlink(log_filename)
                sh.touch_file(log_filename)
                self.tracewriter.file_touched(log_filename)
            #we might need to handle more in the future...
        #nothing modified so just return the original
        return contents

    def warm_configs(self):
        pws = ['horizon_keystone_admin', 'service_token']
        for pw_key in pws:
            self.cfg.get("passwords", pw_key)

    def _get_param_map(self, config_fn):
        #these be used to fill in the configuration/cmds +
        #params with actual values
        mp = dict()
        if config_fn == ROOT_CONF:
            mp['DEST'] = self.appdir
            mp['SQL_CONN'] = self.cfg.get_dbdsn(DB_NAME)
            mp['KEYSTONE_DIR'] = self.appdir
        elif config_fn == MANAGE_DATA_CONF:
            mp['ADMIN_PASSWORD'] = self.cfg.get('passwords', 'horizon_keystone_admin')
            mp['ADMIN_USERNAME'] = 'admin'
            mp['DEMO_USER_NAME'] = 'demo'
            mp.update(get_shared_params(self.cfg))
        else:
            mp['DEST'] = self.appdir
            mp['BIN_DIR'] = self.bindir
            mp['SERVICE_HOST'] = self.cfg.get('host', 'ip')
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


def get_shared_params(config):
    mp = dict()
    host_ip = config.get('host', 'ip')
    keystone_auth_host = config.get('keystone', 'keystone_auth_host')
    if not keystone_auth_host:
        keystone_auth_host = host_ip
    mp['KEYSTONE_AUTH_HOST'] = keystone_auth_host
    mp['KEYSTONE_AUTH_PORT'] = config.get('keystone', 'keystone_auth_port')
    mp['KEYSTONE_AUTH_PROTOCOL'] = config.get('keystone', 'keystone_auth_protocol')
    keystone_service_host = config.get('keystone', 'keystone_service_host')
    if not keystone_service_host:
        keystone_service_host = host_ip
    mp['KEYSTONE_SERVICE_HOST'] = keystone_service_host
    mp['KEYSTONE_SERVICE_PORT'] = config.get('keystone', 'keystone_service_port')
    mp['KEYSTONE_SERVICE_PROTOCOL'] = config.get('keystone', 'keystone_service_protocol')
    mp['SERVICE_TOKEN'] = config.get("passwords", "service_token")
    return mp
