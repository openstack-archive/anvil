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

from anvil import cfg
from anvil import colorizer
from anvil import components as comp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.utils import OrderedDict

from anvil.components.helpers import db as dbhelper
from anvil.components.helpers import glance as ghelper
from anvil.components.helpers import keystone as khelper

LOG = logging.getLogger(__name__)

# Config files/sections
API_CONF = "glance-api.conf"
REG_CONF = "glance-registry.conf"
API_PASTE_CONF = 'glance-api-paste.ini'
REG_PASTE_CONF = 'glance-registry-paste.ini'
LOGGING_CONF = "logging.conf"
POLICY_JSON = 'policy.json'
CONFIGS = [API_CONF, REG_CONF, API_PASTE_CONF,
           REG_PASTE_CONF, POLICY_JSON, LOGGING_CONF]

# This db will be dropped and created
DB_NAME = "glance"

# Sync db command
SYNC_DB_CMD = [sh.joinpths('$BIN_DIR', 'glance-manage'),
               '--debug', '-v',
               # Available commands:
               'db_sync']


class GlanceUninstaller(comp.PythonUninstallComponent):

    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.get_option('app_dir'), 'bin')


class GlanceInstaller(comp.PythonInstallComponent):

    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.get_option('app_dir'), 'bin')

    @property
    def config_files(self):
        return list(CONFIGS)

    def _filter_pip_requires(self, fn, lines):
        return [l for l in lines
                # Take out entries that aren't really always needed or are
                # resolved/installed by anvil during installation in the first
                # place..
                if not utils.has_any(l.lower(), 'swift', 'keystoneclient',
                                     'oslo.config')]

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        if self.get_bool_option('db-sync'):
            self._setup_db()
            self._sync_db()

    def _setup_db(self):
        dbhelper.drop_db(distro=self.distro,
                         dbtype=self.get_option('db', 'type'),
                         dbname=DB_NAME,
                         **utils.merge_dicts(self.get_option('db'),
                                             dbhelper.get_shared_passwords(self)))
        dbhelper.create_db(distro=self.distro,
                           dbtype=self.get_option('db', 'type'),
                           dbname=DB_NAME,
                           **utils.merge_dicts(self.get_option('db'),
                                               dbhelper.get_shared_passwords(self)))

    def _sync_db(self):
        LOG.info("Syncing glance to database: %s", colorizer.quote(DB_NAME))
        cmds = [{'cmd': SYNC_DB_CMD, 'run_as_root': True}]
        utils.execute_template(
            *cmds,
            cwd=self.bin_dir,
            params=self.config_params(
                None))

    def source_config(self, config_fn):
        if config_fn == LOGGING_CONF:
            real_fn = 'logging.cnf.sample'
        else:
            real_fn = config_fn
        fn = sh.joinpths(self.get_option('app_dir'), 'etc', real_fn)
        return (fn, sh.load_file(fn))

    def _fetch_keystone_params(self):
        params = khelper.get_shared_params(ip=self.get_option('ip'),
                                           service_user='glance',
                                           **utils.merge_dicts(
                                               self.get_option('keystone'),
                                           khelper.get_shared_passwords(self)))
        return {
            'auth_host': params['endpoints']['admin']['host'],
            'auth_port': params['endpoints']['admin']['port'],
            'auth_protocol': params['endpoints']['admin']['protocol'],
            # This uses the public uri not the admin one...
            'auth_uri': params['endpoints']['public']['uri'],
            'admin_tenant_name': params['service_tenant'],
            'admin_user': params['service_user'],
            'admin_password': params['service_password'],
        }

    def _config_adjust_paste(self, contents, fn):
        with io.BytesIO(contents) as stream:
            config = cfg.create_parser(cfg.RewritableConfigParser, self)
            config.readfp(stream)
            for (k, v) in self._fetch_keystone_params().items():
                config.set('filter:authtoken', k, v)
            contents = config.stringify(fn)
        return contents

    def _config_adjust_api_reg(self, contents, fn):
        gparams = ghelper.get_shared_params(**self.options)
        with io.BytesIO(contents) as stream:
            config = cfg.create_parser(cfg.RewritableConfigParser, self)
            config.readfp(stream)
            config.set('DEFAULT', 'debug', self.get_bool_option('verbose'))
            config.set('DEFAULT', 'verbose', self.get_bool_option('verbose'))
            if fn in [REG_CONF]:
                config.set(
                    'DEFAULT',
                    'bind_port',
                    gparams[
                        'endpoints'][
                            'registry'][
                                'port'])
            else:
                config.set(
                    'DEFAULT',
                    'bind_port',
                    gparams[
                        'endpoints'][
                            'public'][
                                'port'])
            config.set(
                'DEFAULT', 'sql_connection', dbhelper.fetch_dbdsn(dbname=DB_NAME,
                                                                  utf8=True,
                                                                  dbtype=self.get_option(
                                                                  'db', 'type'),
                                                                  **utils.merge_dicts(
                                                                  self.get_option(
                'db'),
                                                                      dbhelper.get_shared_passwords(self))))
            config.remove_option('DEFAULT', 'log_file')
            config.set(
                'paste_deploy',
                'flavor',
                self.get_option(
                    'paste_flavor'))
            for (k, v) in self._fetch_keystone_params().items():
                config.set('keystone_authtoken', k, v)
            if fn in [API_CONF]:
                config.set('DEFAULT', 'default_store', 'file')
                img_store_dir = sh.joinpths(
                    self.get_option(
                        'component_dir'),
                    'images')
                config.set(
                    'DEFAULT',
                    'filesystem_store_datadir',
                    img_store_dir)
                LOG.debug(
                    "Ensuring file system store directory %r exists and is empty." %
                    (img_store_dir))
                if sh.isdir(img_store_dir):
                    sh.deldir(img_store_dir)
                sh.mkdirslist(
                    img_store_dir,
                    tracewriter=self.tracewriter,
                    adjust_suids=True)
            return config.stringify(fn)

    def _config_adjust_logging(self, contents, fn):
        with io.BytesIO(contents) as stream:
            config = cfg.create_parser(cfg.RewritableConfigParser, self)
            config.readfp(stream)
            config.set('logger_root', 'level', 'DEBUG')
            config.set('logger_root', 'handlers', "devel,production")
            contents = config.stringify(fn)
        return contents

    @property
    def env_exports(self):
        to_set = OrderedDict()
        params = ghelper.get_shared_params(**self.options)
        for (endpoint, details) in params['endpoints'].items():
            to_set[("GLANCE_%s_URI" % (endpoint.upper()))] = details['uri']
        return to_set

    def _config_param_replace(self, config_fn, contents, parameters):
        if config_fn in [REG_CONF, REG_PASTE_CONF, API_CONF, API_PASTE_CONF, LOGGING_CONF]:
            return contents
        else:
            return comp.PythonInstallComponent._config_param_replace(self, config_fn, contents, parameters)

    def _config_adjust(self, contents, name):
        if name in [REG_CONF, API_CONF]:
            return self._config_adjust_api_reg(contents, name)
        elif name == REG_PASTE_CONF:
            return self._config_adjust_paste(contents, name)
        elif name == API_PASTE_CONF:
            return self._config_adjust_paste(contents, name)
        elif name == LOGGING_CONF:
            return self._config_adjust_logging(contents, name)
        else:
            return contents

    def config_params(self, config_fn):
        # These be used to fill in the configuration params
        mp = comp.PythonInstallComponent.config_params(self, config_fn)
        mp['BIN_DIR'] = self.bin_dir
        return mp


class GlanceRuntime(comp.PythonRuntime):

    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.get_option('app_dir'), 'bin')

    @property
    def applications(self):
        apps = []
        for (name, _values) in self.subsystems.items():
            name = "glance-%s" % (name.lower())
            path = sh.joinpths(self.bin_dir, name)
            if sh.is_executable(path):
                apps.append(
                    comp.Program(
                        name,
                        path,
                        argv=self._fetch_argv(
                            name)))
        return apps

    def _fetch_argv(self, name):
        if name.find('api') != -1:
            return ['--config-file', sh.joinpths('$CONFIG_DIR', API_CONF)]
        elif name.find('registry') != -1:
            return ['--config-file', sh.joinpths('$CONFIG_DIR', REG_CONF)]
        else:
            return []

    def _get_image_urls(self):
        uris = self.get_option('image_urls', default_value=[])
        return [u.strip() for u in uris if len(u.strip())]

    def post_start(self):
        comp.PythonRuntime.post_start(self)
        if self.get_bool_option('load-images'):
            # Install any images that need activating...
            self.wait_active()
            params = {}
            params['glance'] = ghelper.get_shared_params(**self.options)
            params[
                'keystone'] = khelper.get_shared_params(ip=self.get_option('ip'),
                                                        service_user='glance',
                                                        **utils.merge_dicts(
                                                        self.get_option(
                                                        'keystone'),
                                                        khelper.get_shared_passwords(self)))
            cache_dir = self.get_option('image_cache_dir')
            if cache_dir:
                params['cache_dir'] = cache_dir
            ghelper.UploadService(**params).install(self._get_image_urls())


class GlanceTester(comp.PythonTestingComponent):
    # NOTE: only run the unit tests

    def _get_test_command(self):
        base_cmd = comp.PythonTestingComponent._get_test_command(self)
        base_cmd = base_cmd + ['--unittests-only']
        return base_cmd
