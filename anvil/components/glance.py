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

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from anvil import cfg
from anvil import colorizer
from anvil import components as comp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

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

# Reg, api, scrub are here as possible subsystems
GAPI = "api"
GREG = "reg"

# This db will be dropped and created
DB_NAME = "glance"

# What applications to start
APP_OPTIONS = {
    'glance-api': ['--config-file', sh.joinpths('$CONFIG_DIR', API_CONF)],
    'glance-registry': ['--config-file', sh.joinpths('$CONFIG_DIR', REG_CONF)],
}

# How the subcompoent small name translates to an actual app
SUB_TO_APP = {
    GAPI: 'glance-api',
    GREG: 'glance-registry',
}

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

    def _filter_pip_requires_line(self, line):
        if utils.has_any(line.lower(), 'swift'):
            return None
        return line

    def pre_install(self):
        comp.PythonInstallComponent.pre_install(self)

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
        utils.execute_template(*cmds, cwd=self.bin_dir, params=self.config_params(None))

    def source_config(self, config_fn):
        if config_fn == LOGGING_CONF:
            real_fn = 'logging.cnf.sample'
        else:
            real_fn = config_fn
        fn = sh.joinpths(self.get_option('app_dir'), 'etc', real_fn)
        return (fn, sh.load_file(fn))

    def _config_adjust_registry(self, contents, fn):
        params = ghelper.get_shared_params(**self.options)
        with io.BytesIO(contents) as stream:
            config = cfg.RewritableConfigParser()
            config.readfp(stream)
            config.set('DEFAULT', 'debug', self.get_bool_option('verbose'))
            config.set('DEFAULT', 'verbose', self.get_bool_option('verbose'))
            config.set('DEFAULT', 'bind_port', params['endpoints']['registry']['port'])
            config.set('DEFAULT', 'sql_connection', dbhelper.fetch_dbdsn(dbname=DB_NAME,
                                                                         utf8=True,
                                                                         dbtype=self.get_option('db', 'type'),
                                                                         **utils.merge_dicts(self.get_option('db'),
                                                                                             dbhelper.get_shared_passwords(self))))
            config.remove_option('DEFAULT', 'log_file')
            config.set('paste_deploy', 'flavor', self.get_option('paste_flavor'))
            return config.stringify(fn)
        return contents

    def _config_adjust_paste(self, contents, fn):
        params = khelper.get_shared_params(ip=self.get_option('ip'),
                                           service_user='glance',
                                           **utils.merge_dicts(self.get_option('keystone'), 
                                                               khelper.get_shared_passwords(self)))
        with io.BytesIO(contents) as stream:
            config = cfg.RewritableConfigParser()
            config.readfp(stream)
            config.set('filter:authtoken', 'auth_host', params['endpoints']['admin']['host'])
            config.set('filter:authtoken', 'auth_port', params['endpoints']['admin']['port'])
            config.set('filter:authtoken', 'auth_protocol', params['endpoints']['admin']['protocol'])

            # This uses the public uri not the admin one...
            config.set('filter:authtoken', 'auth_uri', params['endpoints']['public']['uri'])

            config.set('filter:authtoken', 'admin_tenant_name', params['service_tenant'])
            config.set('filter:authtoken', 'admin_user', params['service_user'])
            config.set('filter:authtoken', 'admin_password', params['service_password'])
            contents = config.stringify(fn)
        return contents

    def _config_adjust_api(self, contents, fn):
        params = ghelper.get_shared_params(**self.options)
        with io.BytesIO(contents) as stream:
            config = cfg.RewritableConfigParser()
            config.readfp(stream)
            img_store_dir = sh.joinpths(self.get_option('component_dir'), 'images')
            config.set('DEFAULT', 'debug', self.get_bool_option('verbose',))
            config.set('DEFAULT', 'verbose', self.get_bool_option('verbose'))
            config.set('DEFAULT', 'default_store', 'file')
            config.set('DEFAULT', 'filesystem_store_datadir', img_store_dir)
            config.set('DEFAULT', 'bind_port', params['endpoints']['public']['port'])
            config.set('DEFAULT', 'sql_connection', dbhelper.fetch_dbdsn(dbname=DB_NAME,
                                                                         utf8=True,
                                                                         dbtype=self.get_option('db', 'type'),
                                                                         **utils.merge_dicts(self.get_option('db'), 
                                                                                             dbhelper.get_shared_passwords(self))))
            config.remove_option('DEFAULT', 'log_file')
            config.set('paste_deploy', 'flavor', self.get_option('paste_flavor'))
            LOG.debug("Ensuring file system store directory %r exists and is empty." % (img_store_dir))
            sh.deldir(img_store_dir)
            self.tracewriter.dirs_made(*sh.mkdirslist(img_store_dir))
            return config.stringify(fn)

    def _config_adjust_logging(self, contents, fn):
        with io.BytesIO(contents) as stream:
            config = cfg.RewritableConfigParser()
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
        if name == REG_CONF:
            return self._config_adjust_registry(contents, name)
        elif name == REG_PASTE_CONF:
            return self._config_adjust_paste(contents, name)
        elif name == API_CONF:
            return self._config_adjust_api(contents, name)
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
    def apps_to_start(self):
        apps = []
        for (name, _values) in self.subsystems.items():
            if name in SUB_TO_APP:
                apps.append({
                    'name': SUB_TO_APP[name],
                    'path': sh.joinpths(self.bin_dir, SUB_TO_APP[name]),
                })
        return apps

    def app_options(self, app):
        return APP_OPTIONS.get(app)

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
            params['keystone'] = khelper.get_shared_params(ip=self.get_option('ip'),
                                                           service_user='glance',
                                                           **utils.merge_dicts(self.get_option('keystone'),
                                                                               khelper.get_shared_passwords(self)))
            ghelper.UploadService(params).install(self._get_image_urls())


class GlanceTester(comp.PythonTestingComponent):
    # TODO(harlowja) these should probably be bugs...
    def _get_test_exclusions(self):
        return [
            # These seem to require swift, not always installed...
            'test_swift_store',
        ]
