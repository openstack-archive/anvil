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

from anvil.components.helpers import db as dbhelper
from anvil.components.helpers import keystone as khelper
from anvil.components.helpers import cinder as chelper

LOG = logging.getLogger(__name__)

# Copies from helpers
API_CONF = chelper.API_CONF

# Paste configuration
PASTE_CONF = chelper.PASTE_CONF

CONFIGS = [PASTE_CONF, API_CONF]

# This db will be dropped and created
DB_NAME = "cinder"

# Sync db command
SYNC_DB_CMD = [sh.joinpths('$BIN_DIR', 'cinder-manage'),
                # Available commands:
                'db', 'sync']

BIN_DIR = 'bin'

class CinderUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.get_option('app_dir'), BIN_DIR)


class CinderInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.get_option('app_dir'), BIN_DIR)
        self.conf_maker = chelper.ConfConfigurator(self)

    @property
    def config_files(self):
        return list(CONFIGS)

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        if self.get_bool_option('db-sync'):
            self._setup_db()
            self._sync_db()

    def _filter_pip_requires(self, fn, lines):
        return [l for l in lines
            # Take out entries that aren't really always needed or are
            # resolved/installed by anvil during installation in the first
            # place..
            if not utils.has_any(l.lower(), 'oslo.config')]

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
        LOG.info("Syncing cinder to database: %s", colorizer.quote(DB_NAME))
        cmds = [{'cmd': SYNC_DB_CMD, 'run_as_root': True}]
        utils.execute_template(*cmds, cwd=self.bin_dir, params=self.config_params(None))

    def source_config(self, config_fn):
        if config_fn == API_CONF:
            config_fn = 'cinder.conf.sample'
        fn = sh.joinpths(self.get_option('app_dir'), 'etc', "cinder", config_fn)
        return (fn, sh.load_file(fn))

    def _fetch_keystone_params(self):
        params = khelper.get_shared_params(ip=self.get_option('ip'),
                                           service_user='cinder',
                                           **utils.merge_dicts(self.get_option('keystone'),
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

            'service_host': params['endpoints']['internal']['host'],
            'service_port': params['endpoints']['internal']['port'],
            'service_protocol': params['endpoints']['internal']['protocol'],
            'auth_version': 'v2.0'

        }

    def _config_adjust(self, contents, name):
        if name == PASTE_CONF:
            return self._config_adjust_paste(contents, name)
        elif name == API_CONF:
            return self._generate_cinder_conf(name)
        else:
            return contents

    def _config_adjust_paste(self, contents, fn):
        with io.BytesIO(contents) as stream:
            config = cfg.create_parser(cfg.RewritableConfigParser, self)
            config.readfp(stream)
            for (k, v) in self._fetch_keystone_params().items():
                config.set('filter:authtoken', k, v)
            contents = config.stringify(fn)
        return contents

    def _config_param_replace(self, config_fn, contents, parameters):
        if config_fn in [PASTE_CONF, API_CONF]:
            # We handle these ourselves
            return contents
        else:
            return comp.PythonInstallComponent._config_param_replace(self, config_fn, contents, parameters)

    def _generate_cinder_conf(self, fn):
        LOG.debug("Generating dynamic content for cinder: %s.", (fn))
        return self.conf_maker.generate(fn)

    def config_params(self, config_fn):
        # These be used to fill in the configuration params
        mp = comp.PythonInstallComponent.config_params(self, config_fn)
        mp['CFG_FILE'] = sh.joinpths(self.get_option('cfg_dir'), API_CONF)
        mp['BIN_DIR'] = self.bin_dir
        return mp


class CinderRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.get_option('app_dir'), BIN_DIR)
        self.config_path = sh.joinpths(self.get_option('cfg_dir'), API_CONF)

    @property
    def applications(self):
        apps = []
        for (name, _values) in self.subsystems.items():
            name = "cinder-%s" % (name.lower())
            path = sh.joinpths(self.bin_dir, name)
            if sh.is_executable(path):
                apps.append(comp.Program(name, path, argv=self._fetch_argv(name)))
        return apps

    def app_params(self, program):
        params = comp.PythonRuntime.app_params(self, program)
        params['CFG_FILE'] = self.config_path
        return params

    def _fetch_argv(self, name):
        return [
            '--config-file', '$CFG_FILE',
        ]
