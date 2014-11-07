# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2014 GoDaddy Operating Company, LLC. All Rights Reserved.
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
from anvil import utils

from anvil.components import base_install as binstall

from anvil.components.configurators import ironic as iconf

LOG = logging.getLogger(__name__)

# Sync db command
SYNC_DB_CMD = ['sudo', '-u', 'ironic', '/usr/bin/ironic-dbsync',
               'create_schema']


class IronicInstaller(binstall.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        binstall.PythonInstallComponent.__init__(self, *args, **kargs)
        self.configurator = iconf.IronicConfigurator(self)

    def post_install(self):
        binstall.PythonInstallComponent.post_install(self)
        if self.get_bool_option('db-sync'):
            self._sync_db()

    def _sync_db(self):
        LOG.info("Syncing ironic to database: %s", colorizer.quote(self.configurator.DB_NAME))
        cmds = [{'cmd': SYNC_DB_CMD}]
        utils.execute_template(*cmds, cwd=self.bin_dir)
