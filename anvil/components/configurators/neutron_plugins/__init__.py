# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2013 Yahoo! Inc. All Rights Reserved.
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

from anvil.components.configurators.neutron import MQ_BACKENDS
from anvil.components.configurators import base
from anvil import shell as sh


class Configurator(base.Configurator):

    DB_NAME = "neutron"
    PLUGIN_CLASS = "neutron.plugins.UNKNOWN"

    def __init__(self, installer, configs, adjusters):
        super(Configurator, self).__init__(installer, configs)
        self.config_adjusters = adjusters
        self.core_plugin = installer.get_option("core_plugin")

    def _config_adjust_plugin(self, plugin_conf):
        params = self.get_keystone_params('neutron')
        plugin_conf.add("admin_password", params["service_password"])
        plugin_conf.add("admin_user", params["service_user"])
        plugin_conf.add("admin_tenant_name", params["service_tenant"])
        plugin_conf.add("auth_url", params["endpoints"]["admin"]["uri"])

        plugin_conf.add("debug", self.installer.get_bool_option("debug"))
        plugin_conf.add("verbose", self.installer.get_bool_option("verbose"))


class CorePluginConfigurator(Configurator):

    def __init__(self, installer, configs, adjusters):
        self.core_plugin = installer.get_option("core_plugin")
        super(CorePluginConfigurator, self).__init__(
            installer,
            [self._config_path(name) for name in configs],
            dict((self._config_path(name), value)
                 for name, value in adjusters.iteritems()))

    def _config_adjust_plugin(self, plugin_conf):
        self.setup_rpc(plugin_conf, rpc_backends=MQ_BACKENDS)
        plugin_conf.add_with_section(
            "DATABASE",
            "sql_connection",
            self.fetch_dbdsn())

    def _config_path(self, name):
        return sh.joinpths('plugins', self.core_plugin, name)

    @property
    def path_to_plugin_config(self):
        raise NotImplementedError()
