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
PLUGIN_CONF = "l3_agent.ini"

CONFIGS = [PLUGIN_CONF]


class L3Configurator(quantum_plugins.Configurator):

    def __init__(self, installer):
        super(L3Configurator, self).__init__(
            installer, CONFIGS, {PLUGIN_CONF: self._config_adjust_plugin})

    def _config_adjust_plugin(self, plugin_conf):
        params = self.get_keystone_params('quantum')
        plugin_conf.add("l3_agent_manager", "quantum.agent.l3_agent.L3NATAgentWithStateReport")
        plugin_conf.add("external_network_bridge", "br-ex")
        plugin_conf.add("admin_password", params["service_password"])
        plugin_conf.add("admin_user", params["service_user"])
        plugin_conf.add("admin_tenant_name", params["service_tenant"])
        plugin_conf.add("auth_url", params["endpoints"]["admin"]["uri"])
        plugin_conf.add("root_helper", "sudo quantum-rootwrap /etc/quantum/rootwrap.conf")
        plugin_conf.add("use_namespaces", "False")
        plugin_conf.add("debug", "False")
        plugin_conf.add("verbose", "True")
        if self.installer.get_option("core_plugin") == 'openvswitch':
            plugin_conf.add("interface_driver", "quantum.agent.linux.interface.OVSInterfaceDriver")

    @property
    def get_plugin_config_file_path(self):
        return PLUGIN_CONF
