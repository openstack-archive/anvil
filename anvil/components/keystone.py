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

import copy
import io
import yaml

from anvil import cfg
from anvil import colorizer
from anvil import component as comp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.helpers import db as dbhelper
from anvil.helpers import glance as ghelper
from anvil.helpers import keystone as khelper
from anvil.helpers import nova as nhelper
from anvil.helpers import quantum as qhelper
from anvil.helpers import swift as shelper

LOG = logging.getLogger(__name__)

# This db will be dropped then created
DB_NAME = "keystone"

# Subdirs of the git checkout
BIN_DIR = "bin"

# This yaml file controls keystone initialization
INIT_WHAT_FN = 'init_what.yaml'

# Existence of this file signifies that initialization ran
INIT_WHAT_HAPPENED = "keystone.inited.yaml"

# Simple confs
ROOT_CONF = "keystone.conf"
ROOT_SOURCE_FN = "keystone.conf.sample"
LOGGING_CONF = "logging.conf"
LOGGING_SOURCE_FN = 'logging.conf.sample'
POLICY_JSON = 'policy.json'
CONFIGS = [ROOT_CONF, LOGGING_CONF, POLICY_JSON]

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
        self.bin_dir = sh.joinpths(self.get_option('app_dir'), BIN_DIR)

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

    def _sync_db(self):
        LOG.info("Syncing keystone to database: %s", colorizer.quote(DB_NAME))
        mp = self._get_param_map(None)
        cmds = [{'cmd': SYNC_DB_CMD, 'run_as_root': True}]
        utils.execute_template(*cmds, cwd=self.bin_dir, params=mp)

    def _get_config_files(self):
        return list(CONFIGS)

    def _setup_db(self):
        dbhelper.drop_db(self.cfg, self.distro, DB_NAME)
        dbhelper.create_db(self.cfg, self.distro, DB_NAME, utf8=True)

    def _get_source_config(self, config_fn):
        real_fn = config_fn
        if config_fn == LOGGING_CONF:
            real_fn = LOGGING_SOURCE_FN
        elif config_fn == ROOT_CONF:
            real_fn = ROOT_SOURCE_FN
        fn = sh.joinpths(self.get_option('app_dir'), 'etc', real_fn)
        return (fn, sh.load_file(fn))

    def _config_adjust_logging(self, contents, fn):
        with io.BytesIO(contents) as stream:
            config = cfg.RewritableConfigParser()
            config.readfp(stream)
            config.set('logger_root', 'level', 'DEBUG')
            config.set('logger_root', 'handlers', "devel,production")
            contents = config.stringify(fn)
        return contents

    def _config_param_replace(self, config_fn, contents, parameters):
        if config_fn in [ROOT_CONF, LOGGING_CONF]:
            # We handle these ourselves
            return contents
        else:
            return comp.PythonInstallComponent._config_param_replace(self, config_fn, contents, parameters)

    def _config_adjust_root(self, contents, fn):
        params = khelper.get_shared_params(self.cfg)
        with io.BytesIO(contents) as stream:
            config = cfg.RewritableConfigParser()
            config.readfp(stream)
            config.set('DEFAULT', 'admin_token', params['service_token'])
            config.set('DEFAULT', 'admin_port', params['endpoints']['admin']['port'])
            config.set('DEFAULT', 'public_port', params['endpoints']['public']['port'])
            config.set('DEFAULT', 'verbose', True)
            config.set('DEFAULT', 'debug', True)
            config.set('catalog', 'driver', 'keystone.catalog.backends.sql.Catalog')
            config.remove_option('DEFAULT', 'log_config')
            config.set('sql', 'connection', dbhelper.fetch_dbdsn(self.cfg, DB_NAME, utf8=True))
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
        khelper.get_shared_params(self.cfg)

    def _get_param_map(self, config_fn):
        # These be used to fill in the configuration/cmds +
        # params with actual values
        mp = comp.PythonInstallComponent._get_param_map(self, config_fn)
        mp['BIN_DIR'] = self.bin_dir
        mp['CONFIG_FILE'] = sh.joinpths(self.get_option('cfg_dir'), ROOT_CONF)
        return mp


class KeystoneRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.get_option('app_dir'), BIN_DIR)
        self.wait_time = max(self.cfg.getint('DEFAULT', 'service_wait_seconds'), 1)
        self.init_fn = sh.joinpths(self.get_option('trace_dir'), INIT_WHAT_HAPPENED)
        (fn, contents) = utils.load_template(self.name, INIT_WHAT_FN)
        self.init_what = yaml.load(contents)

    def post_start(self):
        if not sh.isfile(self.init_fn):
            LOG.info("Waiting %s seconds so that keystone can start up before running first time init." % (self.wait_time))
            sh.sleep(self.wait_time)
            LOG.info("Running commands to initialize keystone.")
            LOG.debug("Initializing with %s", self.init_what)
            initial_cfg = dict()
            initial_cfg['glance'] = ghelper.get_shared_params(self.cfg)
            initial_cfg['keystone'] = khelper.get_shared_params(self.cfg)
            initial_cfg['nova'] = nhelper.get_shared_params(self.cfg)
            initial_cfg['quantum'] = qhelper.get_shared_params(self.cfg)
            initial_cfg['swift'] = shelper.get_shared_params(self.cfg)
            init_what = utils.param_replace_deep(copy.deepcopy(self.init_what), initial_cfg)
            khelper.Initializer(initial_cfg['keystone']).initialize(**init_what)
            # Writing this makes sure that we don't init again
            sh.write_file(self.init_fn, utils.prettify_yaml(init_what))
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
