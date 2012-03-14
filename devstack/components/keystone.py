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

from urlparse import urlunparse

from devstack import cfg
from devstack import cfg_helpers
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

#swift template additions
SWIFT_TEMPL_ADDS = ['catalog.RegionOne.object_store.publicURL = http://%SERVICE_HOST%:8080/v1/AUTH_$(tenant_id)s',
                    'catalog.RegionOne.object_store.publicURL = http://%SERVICE_HOST%:8080/v1/AUTH_$(tenant_id)s',
                    'catalog.RegionOne.object_store.adminURL = http://%SERVICE_HOST%:8080/',
                    'catalog.RegionOne.object_store.internalURL = http://%SERVICE_HOST%:8080/v1/AUTH_$(tenant_id)s',
                    "catalog.RegionOne.object_store.name = 'Swift Service'"]

#quantum template additions
QUANTUM_TEMPL_ADDS = ['catalog.RegionOne.network.publicURL = http://%SERVICE_HOST%:9696/',
                      'catalog.RegionOne.network.adminURL = http://%SERVICE_HOST%:9696/',
                      'catalog.RegionOne.network.internalURL = http://%SERVICE_HOST%:9696/',
                      "catalog.RegionOne.network.name = 'Quantum Service'"]


class KeystoneUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)


class KeystoneInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)
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
        db.drop_db(self.cfg, self.pw_gen, self.distro, DB_NAME)
        db.create_db(self.cfg, self.pw_gen, self.distro, DB_NAME)

    def _setup_initer(self):
        LOG.info("Configuring keystone initializer template %s.", MANAGE_DATA_CONF)
        (_, contents) = utils.load_template(self.component_name, MANAGE_DATA_CONF)
        params = self._get_param_map(MANAGE_DATA_CONF)
        contents = utils.param_replace(contents, params, True)
        tgt_fn = sh.joinpths(self.bindir, MANAGE_DATA_CONF)
        sh.write_file(tgt_fn, contents)
        sh.chmod(tgt_fn, 0755)
        self.tracewriter.file_touched(tgt_fn)

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
                        self.tracewriter.dirs_made(*sh.mkdirslist(log_dir))
                    #destroy then recreate it (the log file)
                    sh.unlink(log_filename)
                    self.tracewriter.file_touched(sh.touch_file(log_filename))
        elif name == CATALOG_CONF:
            nlines = list()
            if utils.service_enabled(settings.SWIFT, self.instances):
                mp = dict()
                mp['SERVICE_HOST'] = self.cfg.get('host', 'ip')
                nlines.append("# Swift additions")
                nlines.extend(utils.param_replace_list(SWIFT_TEMPL_ADDS, mp))
                nlines.append("")
            if utils.service_enabled(settings.QUANTUM, self.instances) or \
                    utils.service_enabled(settings.QUANTUM_CLIENT, self.instances):
                mp = dict()
                mp['SERVICE_HOST'] = self.cfg.get('host', 'ip')
                nlines.append("# Quantum additions")
                nlines.extend(utils.param_replace_list(QUANTUM_TEMPL_ADDS, mp))
                nlines.append("")
            if nlines:
                nlines.insert(0, contents)
                contents = cfg.add_header(name, utils.joinlinesep(*nlines))
        return contents

    def _get_source_config(self, config_fn):
        if config_fn == LOGGING_CONF:
            fn = sh.joinpths(self.cfgdir, LOGGING_SOURCE_FN)
            contents = sh.load_file(fn)
            return (fn, contents)
        return comp.PythonInstallComponent._get_source_config(self, config_fn)

    def warm_configs(self):
        get_shared_params(self.cfg, self.pw_gen)

    def _get_param_map(self, config_fn):
        #these be used to fill in the configuration/cmds +
        #params with actual values
        mp = dict()
        mp['SERVICE_HOST'] = self.cfg.get('host', 'ip')
        mp['DEST'] = self.appdir
        mp['BIN_DIR'] = self.bindir
        mp['CONFIG_FILE'] = sh.joinpths(self.cfgdir, ROOT_CONF)
        if config_fn == ROOT_CONF:
            mp['SQL_CONN'] = cfg_helpers.fetch_dbdsn(self.cfg, self.pw_gen, DB_NAME)
            mp['KEYSTONE_DIR'] = self.appdir
            mp.update(get_shared_params(self.cfg, self.pw_gen))
        elif config_fn == MANAGE_DATA_CONF:
            mp.update(get_shared_params(self.cfg, self.pw_gen))
        return mp


class KeystoneRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)

    def post_start(self):
        tgt_fn = sh.joinpths(self.bindir, MANAGE_DATA_CONF)
        if sh.isfile(tgt_fn):
            #still there, run it
            #these environment additions are important
            #in that they eventually affect how this script runs
            LOG.info("Waiting %s seconds so that keystone can start up before running first time init." % (WAIT_ONLINE_TO))
            sh.sleep(WAIT_ONLINE_TO)
            env = dict()
            env['ENABLED_SERVICES'] = ",".join(self.instances.keys())
            env['BIN_DIR'] = self.bindir
            setup_cmd = MANAGE_CMD_ROOT + [tgt_fn]
            LOG.info("Running (%s) command to initialize keystone." % (" ".join(setup_cmd)))
            sh.execute(*setup_cmd, env_overrides=env, run_as_root=False)
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


def get_shared_params(config, pw_gen, service_user_name=None):
    mp = dict()
    host_ip = config.get('host', 'ip')

    #these match what is in keystone_init.sh
    mp['SERVICE_TENANT_NAME'] = 'service'
    if service_user_name:
        mp['SERVICE_USERNAME'] = str(service_user_name)
    mp['ADMIN_USER_NAME'] = 'admin'
    mp['DEMO_USER_NAME'] = 'demo'
    mp['ADMIN_TENANT_NAME'] = mp['ADMIN_USER_NAME']
    mp['DEMO_TENANT_NAME'] = mp['DEMO_USER_NAME']

    #tokens and passwords
    mp['SERVICE_TOKEN'] = pw_gen.get_password("service_token")
    mp['ADMIN_PASSWORD'] = pw_gen.get_password('horizon_keystone_admin', length=20)
    mp['SERVICE_PASSWORD'] = pw_gen.get_password('service_password')

    #components of the auth endpoint
    keystone_auth_host = config.getdefaulted('keystone', 'keystone_auth_host', host_ip)
    mp['KEYSTONE_AUTH_HOST'] = keystone_auth_host
    keystone_auth_port = config.getdefaulted('keystone', 'keystone_auth_port', '35357')
    mp['KEYSTONE_AUTH_PORT'] = keystone_auth_port
    keystone_auth_proto = config.getdefaulted('keystone', 'keystone_auth_protocol', 'http')
    mp['KEYSTONE_AUTH_PROTOCOL'] = keystone_auth_proto

    #components of the service endpoint
    keystone_service_host = config.getdefaulted('keystone', 'keystone_service_host', host_ip)
    mp['KEYSTONE_SERVICE_HOST'] = keystone_service_host
    keystone_service_port = config.getdefaulted('keystone', 'keystone_service_port', '5000')
    mp['KEYSTONE_SERVICE_PORT'] = keystone_service_port
    keystone_service_proto = config.getdefaulted('keystone', 'keystone_service_protocol', 'http')
    mp['KEYSTONE_SERVICE_PROTOCOL'] = keystone_service_proto

    #http/https endpoints
    mp['AUTH_ENDPOINT'] = urlunparse((keystone_auth_proto,
                                         "%s:%s" % (keystone_auth_host, keystone_auth_port),
                                         "v2.0", "", "", ""))
    mp['SERVICE_ENDPOINT'] = urlunparse((keystone_service_proto,
                                         "%s:%s" % (keystone_service_host, keystone_service_port),
                                         "v2.0", "", "", ""))

    return mp
