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

from anvil.components import base_install as binstall

from anvil.components.configurators import quantum as qconf
LOG = logging.getLogger(__name__)

# Sync db command
# FIXME(aababilov)
SYNC_DB_CMD = ["/usr/bin/quantum-db-manage",
               "sync"]


class QuantumInstaller(binstall.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        super(QuantumInstaller, self).__init__(*args, **kargs)
        self.configurator = qconf.QuantumConfigurator(self)

    def post_install(self):
        super(QuantumInstaller, self).post_install()
        if self.get_bool_option("db-sync"):
            self.configurator.setup_db()
            self._sync_db()

    def _sync_db(self):
        LOG.info("Syncing quantum to database: %s", colorizer.quote(self.configurator.DB_NAME))
        #cmds = [{"cmd": SYNC_DB_CMD}]
        #utils.execute_template(*cmds, cwd=self.bin_dir,
        # params=self.config_params(None))
