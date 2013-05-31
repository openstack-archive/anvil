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

from anvil import colorizer
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.components import base_install as binstall
from anvil.components import base_runtime as bruntime

from anvil.components.configurators import cinder as cconf

LOG = logging.getLogger(__name__)

# Sync db command
SYNC_DB_CMD = [sh.joinpths('$BIN_DIR', 'cinder-manage'),
                # Available commands:
                'db', 'sync']


class CinderInstaller(binstall.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        binstall.PythonInstallComponent.__init__(self, *args, **kargs)
        self.configurator = cconf.CinderConfigurator(self)

    def post_install(self):
        binstall.PythonInstallComponent.post_install(self)
        if self.get_bool_option('db-sync'):
            self.configurator.setup_db()
            self._sync_db()

    def _sync_db(self):
        LOG.info("Syncing cinder to database: %s", colorizer.quote(self.configurator.DB_NAME))
        cmds = [{'cmd': SYNC_DB_CMD}]
        utils.execute_template(*cmds, cwd=self.bin_dir, params=self.config_params(None))

    def config_params(self, config_fn):
        mp = binstall.PythonInstallComponent.config_params(self, config_fn)
        mp['BIN_DIR'] = self.bin_dir
        return mp


class CinderRuntime(bruntime.PythonRuntime):
    def __init__(self, *args, **kargs):
        bruntime.PythonRuntime.__init__(self, *args, **kargs)
        self.config_path = sh.joinpths(self.get_option('cfg_dir'), cconf.API_CONF)

    @property
    def applications(self):
        apps = []
        for (name, _values) in self.subsystems.items():
            name = "cinder-%s" % (name.lower())
            path = sh.joinpths(self.bin_dir, name)
            if sh.is_executable(path):
                apps.append(bruntime.Program(name, path, argv=self._fetch_argv(name)))
        return apps

    def app_params(self, program):
        params = bruntime.PythonRuntime.app_params(self, program)
        params['CFG_FILE'] = self.config_path
        return params

    def _fetch_argv(self, name):
        return [
            '--config-file', '$CFG_FILE',
        ]
