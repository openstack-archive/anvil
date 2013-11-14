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

from anvil.components.configurators import neutron_plugins

# Special generated conf
PLUGIN_CONF = "metadata_agent.ini"

CONFIGS = [PLUGIN_CONF]


class MetadataConfigurator(neutron_plugins.Configurator):

    def __init__(self, installer):
        super(MetadataConfigurator, self).__init__(
            installer, CONFIGS, {PLUGIN_CONF: self._config_adjust_plugin})
