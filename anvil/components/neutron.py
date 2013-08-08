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

from anvil.components import base
from anvil.components import base_install as binstall
from anvil.components import base_runtime as bruntime

from anvil.components.configurators import neutron as qconf


LOG = logging.getLogger(__name__)

# Sync db command
# FIXME(aababilov)
SYNC_DB_CMD = ["sudo", "-u", "neutron", "/usr/bin/neutron-db-manage",
               "sync"]


class NeutronPluginMixin(base.Component):
    def subsystem_names(self):
        core_plugin = self.get_option("core_plugin")
        return [(name if name != "agent" else "%s-agent" % (core_plugin))
                for name in self.subsystems.iterkeys()]


class NeutronInstaller(binstall.PythonInstallComponent, NeutronPluginMixin):
    def __init__(self, *args, **kargs):
        super(NeutronInstaller, self).__init__(*args, **kargs)
        self.configurator = qconf.NeutronConfigurator(self)

    def post_install(self):
        super(NeutronInstaller, self).post_install()
        if self.get_bool_option("db-sync"):
            self.configurator.setup_db()
            self._sync_db()
        self.create_symlink_to_conf_file()

    def _sync_db(self):
        LOG.info("Syncing neutron to database: %s", colorizer.quote(self.configurator.DB_NAME))
        # TODO(aababilov): update db if required

    def create_symlink_to_conf_file(self):
        sh.symlink(self.configurator.path_to_plugin_config,
                   "/etc/neutron/plugin.ini",
                   force=True)


class NeutronUninstaller(binstall.PkgUninstallComponent, NeutronPluginMixin):
    pass


class NeutronRuntime(bruntime.OpenStackRuntime, NeutronPluginMixin):
    pass
