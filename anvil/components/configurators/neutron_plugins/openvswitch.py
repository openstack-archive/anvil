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

from anvil.components.configurators.neutron_plugins import base


class OpenvswitchConfigurator(base.CorePluginConfigurator):

    PLUGIN_CONF = "ovs_neutron_plugin.ini"
    PLUGIN_CLASS = "neutron.plugins.openvswitch.ovs_neutron_plugin.OVSNeutronPluginV2"

    def __init__(self, installer):
        super(OpenvswitchConfigurator, self).__init__(installer)

    def _adjust_plugin_config(self, plugin_conf):
        super(OpenvswitchConfigurator, self)._adjust_plugin_config(plugin_conf)

        plugin_conf.add("integration_bridge",
                        self.installer.get_option("integration_bridge"))
