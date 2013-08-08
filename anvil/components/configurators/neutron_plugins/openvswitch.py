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
from anvil.components.configurators import neutron_plugins

# Special generated conf
PLUGIN_CONF = "ovs_neutron_plugin.ini"

CONFIGS = [PLUGIN_CONF]


class OpenvswitchConfigurator(neutron_plugins.CorePluginConfigurator):

    PLUGIN_CLASS = "neutron.plugins.openvswitch.ovs_neutron_plugin.OVSNeutronPluginV2"

    def __init__(self, installer):
        super(OpenvswitchConfigurator, self).__init__(
            installer, CONFIGS, {PLUGIN_CONF: self._config_adjust_plugin})

    def _config_adjust_plugin(self, plugin_conf):
        self.setup_rpc(plugin_conf, rpc_backends=MQ_BACKENDS)
        plugin_conf.add_with_section(
            "DATABASE",
            "sql_connection",
            self.fetch_dbdsn())

    @property
    def path_to_plugin_config(self):
        return self._config_path(PLUGIN_CONF)
