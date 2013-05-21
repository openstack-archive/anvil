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
from anvil import components as comp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.components.configurators import quantum as qconf
LOG = logging.getLogger(__name__)

# Sync db command
# FIXME(aababilov)
SYNC_DB_CMD = [sh.joinpths("$BIN_DIR", "quantum-db-manage"),
               "sync"]

BIN_DIR = "bin"

class QuantumUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        super(QuantumUninstaller, self).__init__(*args, **kargs)
        self.bin_dir = sh.joinpths(self.get_option("app_dir"), BIN_DIR)


class QuantumInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        super(QuantumInstaller, self).__init__(*args, **kargs)
        self.bin_dir = sh.joinpths(self.get_option("app_dir"), BIN_DIR)
        self.configurator = qconf.QuantumConfigurator(self)

    def post_install(self):
        super(QuantumInstaller, self).post_install()
        if self.get_bool_option("db-sync"):
            self.configurator.setup_db()
            self._sync_db()

    def _filter_pip_requires(self, fn, lines):
        # Take out entries that aren't really always needed or are
        # resolved/installed by anvil during installation in the first
        # place..
        return [l for l in lines
                if not utils.has_any(l.lower(), "oslo.config")]

    def _sync_db(self):
        LOG.info("Syncing quantum to database: %s", colorizer.quote(self.configurator.DB_NAME))
        #cmds = [{"cmd": SYNC_DB_CMD, "run_as_root": True}]
        #utils.execute_template(*cmds, cwd=self.bin_dir,
        # params=self.config_params(None))

    def config_params(self, config_fn):
        # These be used to fill in the configuration params
        mp = super(QuantumInstaller, self).config_params(config_fn)
        mp["BIN_DIR"] = self.bin_dir
        return mp


class QuantumRuntime(comp.PythonRuntime):

    system = "quantum"

    def __init__(self, *args, **kargs):
        super(QuantumRuntime, self).__init__(*args, **kargs)

        # TODO(aababilov): move to base class
        self.bin_dir = sh.joinpths(self.get_option("app_dir"), BIN_DIR)
        self.config_path = sh.joinpths(self.get_option("cfg_dir"), qconf.API_CONF)

    # TODO(aababilov): move to base class
    @property
    def applications(self):
        apps = []
        for (name, _values) in self.subsystems.items():
            name = "%s-%s" % (self.system, name.lower())
            path = sh.joinpths(self.bin_dir, name)
            if sh.is_executable(path):
                apps.append(comp.Program(
                    name, path, argv=self._fetch_argv(name)))
        return apps

    def app_params(self, program):
        params = comp.PythonRuntime.app_params(self, program)
        params["CFG_FILE"] = self.config_path
        return params

    def _fetch_argv(self, name):
        return [
            "--config-file", "$CFG_FILE",
        ]
