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
from devstack import component as comp
from devstack import log as logging
from devstack import shell as sh
from devstack import utils

from devstack.components import db

LOG = logging.getLogger("devstack.components.keystone")

# This db will be dropped then created
DB_NAME = "keystone"

# Subdirs of the git checkout
BIN_DIR = "bin"

# Simple confs
ROOT_CONF = "keystone.conf"
ROOT_SOURCE_FN = "keystone.conf.sample"
CATALOG_CONF = 'default_catalog.templates'
LOGGING_CONF = "logging.conf"
LOGGING_SOURCE_FN = 'logging.conf.sample'
CONFIGS = [ROOT_CONF, CATALOG_CONF, LOGGING_CONF]

# This is a special conf/init script
MANAGE_DATA_CONF = 'keystone_init.sh'
MANAGE_CMD_ROOT = [sh.joinpths("/", "bin", 'bash')]
MANAGE_ADMIN_USER = 'admin'
MANAGE_DEMO_USER = 'demo'
MANGER_SERVICE_TENANT = 'service'

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


# Swift template additions
# TODO: get rid of these
SWIFT_TEMPL_ADDS = ['catalog.RegionOne.object_store.publicURL = http://%SERVICE_HOST%:8080/v1/AUTH_$(tenant_id)s',
                    'catalog.RegionOne.object_store.publicURL = http://%SERVICE_HOST%:8080/v1/AUTH_$(tenant_id)s',
                    'catalog.RegionOne.object_store.adminURL = http://%SERVICE_HOST%:8080/',
                    'catalog.RegionOne.object_store.internalURL = http://%SERVICE_HOST%:8080/v1/AUTH_$(tenant_id)s',
                    "catalog.RegionOne.object_store.name = Swift Service"]

# Quantum template additions
# TODO: get rid of these
QUANTUM_TEMPL_ADDS = ['catalog.RegionOne.network.publicURL = http://%SERVICE_HOST%:9696/',
                      'catalog.RegionOne.network.adminURL = http://%SERVICE_HOST%:9696/',
                      'catalog.RegionOne.network.internalURL = http://%SERVICE_HOST%:9696/',
                      "catalog.RegionOne.network.name = Quantum Service"]


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
        self._setup_initer()

    def known_options(self):
        return set(['swift', 'quantum'])

    def _sync_db(self):
        LOG.info("Syncing keystone to database named %r", DB_NAME)
        mp = self._get_param_map(None)
        cmds = [{'cmd': SYNC_DB_CMD}]
        utils.execute_template(*cmds, cwd=self.bin_dir, params=mp)

    def _get_config_files(self):
        return list(CONFIGS)

    def _setup_db(self):
        LOG.info("Fixing up database named %r", DB_NAME)
        db.drop_db(self.cfg, self.pw_gen, self.distro, DB_NAME)
        db.create_db(self.cfg, self.pw_gen, self.distro, DB_NAME, utf8=True)

    def _setup_initer(self):
        LOG.info("Configuring keystone initializer template %r", MANAGE_DATA_CONF)
        (_, contents) = utils.load_template(self.component_name, MANAGE_DATA_CONF)
        mp = self._get_param_map(MANAGE_DATA_CONF)
        contents = utils.param_replace(contents, mp, True)
        # FIXME, stop placing in checkout dir...
        tgt_fn = sh.joinpths(self.bin_dir, MANAGE_DATA_CONF)
        sh.write_file(tgt_fn, contents)
        sh.chmod(tgt_fn, 0755)
        self.tracewriter.file_touched(tgt_fn)

    def _get_source_config(self, config_fn):
        if config_fn == CATALOG_CONF:
            return comp.PythonInstallComponent._get_source_config(self, config_fn)
        else:
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
            config.remove_option('DEFAULT', 'log_config')
            config.set('sql', 'connection', db.fetch_dbdsn(self.cfg, self.pw_gen, DB_NAME, utf8=True))
            config.set('catalog', 'template_file', sh.joinpths(self.cfg_dir, CATALOG_CONF))
            config.set('catalog', 'driver', "keystone.catalog.backends.templated.TemplatedCatalog")
            config.set('ec2', 'driver', "keystone.contrib.ec2.backends.sql.Ec2")
            config.set('filter:s3_extension', 'paste.filter_factory', "keystone.contrib.s3:S3Extension.factory")
            config.set('pipeline:admin_api', 'pipeline', ('token_auth admin_token_auth xml_body '
                            'json_body debug ec2_extension s3_extension crud_extension admin_service'))
            contents = config.stringify(fn)
        return contents

    def _config_adjust_catalog(self, contents, fn):
        nlines = list()
        if 'swift' in self.options:
            mp = dict()
            mp['SERVICE_HOST'] = self.cfg.get('host', 'ip')
            nlines.append("# Swift additions")
            nlines.extend(utils.param_replace_list(SWIFT_TEMPL_ADDS, mp))
            nlines.append("")
        if 'quantum' in self.options:
            mp = dict()
            mp['SERVICE_HOST'] = self.cfg.get('host', 'ip')
            nlines.append("# Quantum additions")
            nlines.extend(utils.param_replace_list(QUANTUM_TEMPL_ADDS, mp))
            nlines.append("")
        if nlines:
            nlines.insert(0, contents)
            contents = utils.add_header(fn, utils.joinlinesep(*nlines))
        return contents

    def _config_adjust(self, contents, name):
        if name == ROOT_CONF:
            return self._config_adjust_root(contents, name)
        elif name == CATALOG_CONF:
            return self._config_adjust_catalog(contents, name)
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

    def post_start(self):
        tgt_fn = sh.joinpths(self.bin_dir, MANAGE_DATA_CONF)
        if sh.is_executable(tgt_fn):
            # If its still there, run it
            # these environment additions are important
            # in that they eventually affect how this script runs
            LOG.info("Waiting %s seconds so that keystone can start up before running first time init." % (self.wait_time))
            sh.sleep(self.wait_time)
            env = dict()
            env['ENABLED_SERVICES'] = ",".join(self.instances.keys())
            env['BIN_DIR'] = self.bin_dir
            setup_cmd = MANAGE_CMD_ROOT + [tgt_fn]
            LOG.info("Running %r command to initialize keystone." % (" ".join(setup_cmd)))
            sh.execute(*setup_cmd, env_overrides=env, run_as_root=False)
            utils.mark_unexecute_file(tgt_fn, env)

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


def get_shared_params(config, pw_gen, service_user_name=None):
    mp = dict()
    host_ip = config.get('host', 'ip')

    # These match what is in keystone_init.sh
    mp['SERVICE_TENANT_NAME'] = MANGER_SERVICE_TENANT
    if service_user_name:
        mp['SERVICE_USERNAME'] = str(service_user_name)
    mp['ADMIN_USER_NAME'] = MANAGE_ADMIN_USER
    mp['DEMO_USER_NAME'] = MANAGE_DEMO_USER
    mp['ADMIN_TENANT_NAME'] = mp['ADMIN_USER_NAME']
    mp['DEMO_TENANT_NAME'] = mp['DEMO_USER_NAME']

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
