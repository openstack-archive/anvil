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

import yaml

from anvil import cfg
from anvil import colorizer
from anvil import component as comp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils
from anvil import importer

from anvil.components import db

LOG = logging.getLogger(__name__)

# This db will be dropped then created
DB_NAME = "keystone"

# Subdirs of the git checkout
BIN_DIR = "bin"

# This yaml file controls keystone initialization
INIT_WHAT_FN = 'init_what.yaml'

# Simple confs
ROOT_CONF = "keystone.conf"
ROOT_SOURCE_FN = "keystone.conf.sample"
LOGGING_CONF = "logging.conf"
LOGGING_SOURCE_FN = 'logging.conf.sample'
CONFIGS = [ROOT_CONF, LOGGING_CONF]

# Sync db command
SYNC_DB_CMD = [sh.joinpths('%BIN_DIR%', 'keystone-manage'),
                '--config-file=%s' % (sh.joinpths('%CONFIG_DIR%', ROOT_CONF)),
                '--debug', '-v',
                # Available commands:
                # db_sync: Sync the database.
                # export_legacy_catalog: Export the service catalog from a legacy database.
                # import_legacy: Import a legacy database.
                # import_nova_auth: Import a dump of nova auth data into keystone.
                'db_sync']

# What to start
APP_NAME = 'keystone-all'
APP_OPTIONS = {
    APP_NAME: ['--config-file=%s' % (sh.joinpths('%CONFIG_DIR%', ROOT_CONF)),
                "--debug", '-v',
                '--log-config=%s' % (sh.joinpths('%CONFIG_DIR%', LOGGING_CONF))],
}


class KeystoneUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)


class KeystoneInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.app_dir, BIN_DIR)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "keystone_repo"),
            'branch': ("git", "keystone_branch"),
        })
        return places

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        self._setup_db()
        self._sync_db()

    def known_options(self):
        return set(['swift', 'quantum'])

    def _sync_db(self):
        LOG.info("Syncing keystone to database: %s", colorizer.quote(DB_NAME))
        mp = self._get_param_map(None)
        cmds = [{'cmd': SYNC_DB_CMD}]
        utils.execute_template(*cmds, cwd=self.bin_dir, params=mp)

    def _get_config_files(self):
        return list(CONFIGS)

    def _setup_db(self):
        db.drop_db(self.cfg, self.pw_gen, self.distro, DB_NAME)
        db.create_db(self.cfg, self.pw_gen, self.distro, DB_NAME, utf8=True)

    def _get_source_config(self, config_fn):
        real_fn = config_fn
        if config_fn == LOGGING_CONF:
            real_fn = LOGGING_SOURCE_FN
        elif config_fn == ROOT_CONF:
            real_fn = ROOT_SOURCE_FN
        fn = sh.joinpths(self.app_dir, 'etc', real_fn)
        return (fn, sh.load_file(fn))

    def _config_adjust_logging(self, contents, fn):
        with io.BytesIO(contents) as stream:
            config = cfg.IgnoreMissingConfigParser()
            config.readfp(stream)
            config.set('logger_root', 'level', 'DEBUG')
            config.set('logger_root', 'handlers', "devel,production")
            contents = config.stringify(fn)
        return contents

    def _config_adjust_root(self, contents, fn):
        params = get_shared_params(self.cfg, self.pw_gen)
        with io.BytesIO(contents) as stream:
            config = cfg.IgnoreMissingConfigParser()
            config.readfp(stream)
            config.set('DEFAULT', 'admin_token', params['SERVICE_TOKEN'])
            config.set('DEFAULT', 'admin_port', params['KEYSTONE_AUTH_PORT'])
            config.set('DEFAULT', 'verbose', True)
            config.set('DEFAULT', 'debug', True)
            config.set('catalog', 'driver', 'keystone.catalog.backends.sql.Catalog')
            config.remove_option('DEFAULT', 'log_config')
            config.set('sql', 'connection', db.fetch_dbdsn(self.cfg, self.pw_gen, DB_NAME, utf8=True))
            config.set('ec2', 'driver', "keystone.contrib.ec2.backends.sql.Ec2")
            config.set('filter:s3_extension', 'paste.filter_factory', "keystone.contrib.s3:S3Extension.factory")
            config.set('pipeline:admin_api', 'pipeline', ('token_auth admin_token_auth xml_body '
                            'json_body debug ec2_extension s3_extension crud_extension admin_service'))
            contents = config.stringify(fn)
        return contents

    def _config_adjust(self, contents, name):
        if name == ROOT_CONF:
            return self._config_adjust_root(contents, name)
        elif name == LOGGING_CONF:
            return self._config_adjust_logging(contents, name)
        else:
            return contents

    def warm_configs(self):
        get_shared_params(self.cfg, self.pw_gen)

    def _get_param_map(self, config_fn):
        # These be used to fill in the configuration/cmds +
        # params with actual values
        mp = comp.PythonInstallComponent._get_param_map(self, config_fn)
        mp['SERVICE_HOST'] = self.cfg.get('host', 'ip')
        mp['DEST'] = self.app_dir
        mp['BIN_DIR'] = self.bin_dir
        mp['CONFIG_FILE'] = sh.joinpths(self.cfg_dir, ROOT_CONF)
        mp.update(get_shared_params(self.cfg, self.pw_gen))
        return mp


class KeystoneRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.app_dir, BIN_DIR)
        self.wait_time = max(self.cfg.getint('DEFAULT', 'service_wait_seconds'), 1)
        self.init_fn = sh.joinpths(self.trace_dir, 'was-inited')
        self.init_what = yaml.load(utils.load_template(self.component_name, INIT_WHAT_FN)[1])

    def post_start(self):
        if not sh.isfile(self.init_fn):
            LOG.info("Waiting %s seconds so that keystone can start up before running first time init." % (self.wait_time))
            sh.sleep(self.wait_time)
            LOG.info("Running client commands to initialize keystone.")
            LOG.debug("Initializing with %s", self.init_what)
            # Late load since its using a client lib that is only avail after install...
            init_cls = importer.import_entry_point('anvil.helpers.initializers:Keystone')
            initer = init_cls(self)
            initer.initialize(**self.init_what)
            # Touching this makes sure that we don't init again
            # TODO add trace
            sh.touch_file(self.init_fn)
            LOG.info("If you wish to re-run initialization, delete %s", colorizer.quote(self.init_fn))

    def _get_apps_to_start(self):
        apps = list()
        for app_name in APP_OPTIONS.keys():
            apps.append({
                'name': app_name,
                'path': sh.joinpths(self.bin_dir, app_name),
            })
        return apps

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)


def get_shared_params(config, pw_gen,
                     service_user_name=None, service_tenant_name='service'):

    mp = dict()
    host_ip = config.get('host', 'ip')

    mp['SERVICE_TENANT_NAME'] = service_tenant_name
    if service_user_name:
        mp['SERVICE_USERNAME'] = str(service_user_name)

    mp['ADMIN_USER_NAME'] = 'admin'
    mp['ADMIN_TENANT_NAME'] = mp['ADMIN_USER_NAME']
    mp['DEMO_TENANT_NAME'] = 'demo'
    mp['DEMO_USER_NAME'] = mp['DEMO_TENANT_NAME']

    # Tokens and passwords
    mp['SERVICE_TOKEN'] = pw_gen.get_password(
        "service_token",
        'the service admin token',
        )
    mp['ADMIN_PASSWORD'] = pw_gen.get_password(
        'horizon_keystone_admin',
        'the horizon and keystone admin',
        length=20,
        )
    mp['SERVICE_PASSWORD'] = pw_gen.get_password(
        'service_password',
        'service authentication',
        )

    # Components of the auth endpoint
    keystone_auth_host = config.getdefaulted('keystone', 'keystone_auth_host', host_ip)
    mp['KEYSTONE_AUTH_HOST'] = keystone_auth_host
    keystone_auth_port = config.getdefaulted('keystone', 'keystone_auth_port', '35357')
    mp['KEYSTONE_AUTH_PORT'] = keystone_auth_port
    keystone_auth_proto = config.getdefaulted('keystone', 'keystone_auth_protocol', 'http')
    mp['KEYSTONE_AUTH_PROTOCOL'] = keystone_auth_proto

    # Components of the service endpoint
    keystone_service_host = config.getdefaulted('keystone', 'keystone_service_host', host_ip)
    mp['KEYSTONE_SERVICE_HOST'] = keystone_service_host
    keystone_service_port = config.getdefaulted('keystone', 'keystone_service_port', '5000')
    mp['KEYSTONE_SERVICE_PORT'] = keystone_service_port
    keystone_service_proto = config.getdefaulted('keystone', 'keystone_service_protocol', 'http')
    mp['KEYSTONE_SERVICE_PROTOCOL'] = keystone_service_proto

    # Uri's of the http/https endpoints
    mp['AUTH_ENDPOINT'] = urlunparse((keystone_auth_proto,
                                         "%s:%s" % (keystone_auth_host, keystone_auth_port),
                                         "v2.0", "", "", ""))
    mp['SERVICE_ENDPOINT'] = urlunparse((keystone_service_proto,
                                         "%s:%s" % (keystone_service_host, keystone_service_port),
                                         "v2.0", "", "", ""))

    return mp
