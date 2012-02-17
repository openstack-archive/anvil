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
import time

from urlparse import urlunparse

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
LOGGING_CONF = "logging.conf"
LOGGING_SOURCE_FN = 'logging.conf.sample'
CONFIGS = [ROOT_CONF, CATALOG_CONF, LOGGING_CONF]

#this is a special conf
MANAGE_DATA_CONF = 'keystone_init.sh'
MANAGE_CMD_ROOT = [sh.joinpths("/", "bin", 'bash')]
MANAGE_ADMIN_USER = 'admin'
MANAGE_DEMO_USER = 'demo'
MANAGE_INVIS_USER = 'invisible_to_admin'

#sync db command
MANAGE_APP_NAME = 'keystone-manage'
SYNC_DB_CMD = [sh.joinpths('%BINDIR%', MANAGE_APP_NAME), 'db_sync']

#what to start
APP_NAME = 'keystone-all'
APP_OPTIONS = {
    APP_NAME: ['--config-file', sh.joinpths('%ROOT%', CONFIG_DIR, ROOT_CONF),
                "--debug", '-d',
                '--log-config=' + sh.joinpths('%ROOT%', CONFIG_DIR, 'logging.cnf')]
}

#the pkg json files keystone requires for installation
REQ_PKGS = ['general.json', 'keystone.json']

#pip files that keystone requires
REQ_PIPS = ['general.json', 'keystone.json']

#used to wait until started before we can run the data setup script
WAIT_ONLINE_TO = settings.WAIT_ALIVE_SECS

#config keys we warm up so u won't be prompted later
WARMUP_PWS = ['horizon_keystone_admin', 'service_token']


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
        self._setup_initer()

    def _sync_db(self):
        LOG.info("Syncing keystone to database named %s.", DB_NAME)
        params = dict()
        params['BINDIR'] = self.bindir
        cmds = [{'cmd': SYNC_DB_CMD}]
        utils.execute_template(*cmds, cwd=self.bindir, params=params)

    def _get_config_files(self):
        return list(CONFIGS)

    def _setup_db(self):
        LOG.info("Fixing up database named %s.", DB_NAME)
        db.drop_db(self.cfg, DB_NAME)
        db.create_db(self.cfg, DB_NAME)

    def _setup_initer(self):
        LOG.info("Configuring keystone initializer template %s.", MANAGE_DATA_CONF)
        (_, contents) = utils.load_template(self.component_name, MANAGE_DATA_CONF)
        params = self._get_param_map(MANAGE_DATA_CONF)
        contents = utils.param_replace(contents, params, True)
        tgt_fn = sh.joinpths(self.bindir, MANAGE_DATA_CONF)
        sh.write_file(tgt_fn, contents)
        sh.chmod(tgt_fn, 0755)

    def _config_adjust(self, contents, name):
        if name == ROOT_CONF:
            #use config parser and
            #then extract known configs that
            #will need locations/directories/files made (or touched)...
            with io.BytesIO(contents) as stream:
                config = cfg.IgnoreMissingConfigParser()
                config.readfp(stream)
                log_filename = config.get('default', 'log_file')
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

    def _get_source_config(self, config_fn):
        if config_fn == LOGGING_CONF:
            fn = sh.joinpths(self.cfgdir, LOGGING_SOURCE_FN)
            contents = sh.load_file(fn)
            return (fn, contents)
        return comp.PythonInstallComponent._get_source_config(self, config_fn)

    def warm_configs(self):
        for pw_key in WARMUP_PWS:
            self.cfg.get("passwords", pw_key)

    def _get_param_map(self, config_fn):
        #these be used to fill in the configuration/cmds +
        #params with actual values
        mp = dict()
        mp['SERVICE_HOST'] = self.cfg.get('host', 'ip')
        mp['DEST'] = self.appdir
        mp['BIN_DIR'] = self.bindir
        mp['CONFIG_FILE'] = sh.joinpths(self.cfgdir, ROOT_CONF)
        if config_fn == ROOT_CONF:
            mp['SQL_CONN'] = self.cfg.get_dbdsn(DB_NAME)
            mp['KEYSTONE_DIR'] = self.appdir
            mp.update(get_shared_params(self.cfg))
        elif config_fn == MANAGE_DATA_CONF:
            mp['ADMIN_PASSWORD'] = self.cfg.get('passwords', 'horizon_keystone_admin')
            mp.update(get_shared_users(self.cfg))
            mp.update(get_shared_params(self.cfg))
        return mp


class KeystoneRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)

    def post_start(self):
        tgt_fn = sh.joinpths(self.bindir, MANAGE_DATA_CONF)
        if sh.isfile(tgt_fn):
            #still there, run it
            #these environment additions are important
            #in that they eventually affect how this script runs
            LOG.info("Waiting %s seconds so that keystone can start up before running first time init." % (WAIT_ONLINE_TO))
            time.sleep(WAIT_ONLINE_TO)
            env = dict()
            env['ENABLED_SERVICES'] = ",".join(self.instances.keys())
            env['BIN_DIR'] = self.bindir
            setup_cmd = MANAGE_CMD_ROOT + [tgt_fn]
            LOG.info("Running (%s) command to initialize keystone." % (" ".join(setup_cmd)))
            (sysout, _) = sh.execute(*setup_cmd, env_overrides=env, run_as_root=False)
            if sysout:
                sh.write_file(sh.abspth(settings.EC2RC_FN), sysout.strip())
            LOG.debug("Removing (%s) file since we successfully initialized keystone." % (tgt_fn))
            sh.unlink(tgt_fn)

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


def get_shared_users(config):
    mp = dict()
    mp['ADMIN_USER_NAME'] = config.getdefaulted("keystone", "admin_user", MANAGE_ADMIN_USER)
    mp['ADMIN_TENANT_NAME'] = mp['ADMIN_USER_NAME']
    mp['DEMO_USER_NAME'] = config.getdefaulted("keystone", "demo_user", MANAGE_DEMO_USER)
    mp['DEMO_TENANT_NAME'] = mp['DEMO_USER_NAME']
    mp['INVIS_USER_NAME'] = config.getdefaulted("keystone", "invisible_user", MANAGE_INVIS_USER)
    mp['INVIS_TENANT_NAME'] = mp['INVIS_USER_NAME']
    return mp


def get_shared_params(config):
    mp = dict()
    host_ip = config.get('host', 'ip')

    keystone_auth_host = config.getdefaulted('keystone', 'keystone_auth_host', host_ip)
    mp['KEYSTONE_AUTH_HOST'] = keystone_auth_host
    keystone_auth_port = config.get('keystone', 'keystone_auth_port')
    mp['KEYSTONE_AUTH_PORT'] = keystone_auth_port
    keystone_auth_proto = config.get('keystone', 'keystone_auth_protocol')
    mp['KEYSTONE_AUTH_PROTOCOL'] = keystone_auth_proto

    keystone_service_host = config.getdefaulted('keystone', 'keystone_service_host', host_ip)
    mp['KEYSTONE_SERVICE_HOST'] = keystone_service_host
    keystone_service_port = config.get('keystone', 'keystone_service_port')
    mp['KEYSTONE_SERVICE_PORT'] = keystone_service_port
    keystone_service_proto = config.get('keystone', 'keystone_service_protocol')
    mp['KEYSTONE_SERVICE_PROTOCOL'] = keystone_service_proto

    #TODO is this right???
    mp['AUTH_ENDPOINT'] = urlunparse((keystone_auth_proto,
                                         "%s:%s" % (keystone_auth_host, keystone_auth_port),
                                         "v2.0", "", "", ""))
    #TODO is this right???
    mp['SERVICE_ENDPOINT'] = urlunparse((keystone_service_proto,
                                         "%s:%s" % (keystone_service_host, keystone_service_port),
                                         "v2.0", "", "", ""))

    mp['SERVICE_TOKEN'] = config.get("passwords", "service_token")

    return mp
