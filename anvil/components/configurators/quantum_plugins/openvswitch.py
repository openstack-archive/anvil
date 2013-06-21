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

from anvil.components.configurators import quantum_plugins

# Special generated conf
PLUGIN_CONF = "ovs_quantum_plugin.ini"

CONFIGS = [PLUGIN_CONF]


class OpenvswitchConfigurator(quantum_plugins.CorePluginConfigurator):

    PLUGIN_CLASS = "quantum.plugins.openvswitch.ovs_quantum_plugin.OVSQuantumPluginV2"

    def __init__(self, installer):
        super(OpenvswitchConfigurator, self).__init__(
            installer, CONFIGS, {PLUGIN_CONF: self._config_adjust_plugin})

    def _config_adjust_plugin(self, plugin_conf):
        plugin_conf.add_with_section(
            "DATABASE",
            "sql_connection",
            self.fetch_dbdsn())

    @property
    def get_plugin_config_file_path(self):
        return "plugins/%s/%s" % (self.core_plugin, PLUGIN_CONF)
