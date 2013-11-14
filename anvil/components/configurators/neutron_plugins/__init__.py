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

import abc
import six

from anvil.components.configurators.neutron import MQ_BACKENDS
from anvil.components.configurators import base
from anvil import shell as sh


@six.add_metaclass(abc.ABCMeta)
class Configurator(base.Configurator):

    DB_NAME = "neutron"
    PLUGIN_CLASS = "neutron.plugins.UNKNOWN"
    PLUGIN_CONF = None

    def __init__(self, installer):
        super(Configurator, self).__init__(installer)
        self.core_plugin = installer.get_option("core_plugin")
        if self.PLUGIN_CONF is not None:
            config_path = self._config_path(self.PLUGIN_CONF)
            self.configs = [config_path]
            self.config_adjusters = {
                config_path: self._adjust_plugin_config
            }

    @abc.abstractmethod
    def _adjust_plugin_config(self, plugin_conf):
        pass

    @abc.abstractmethod
    def _config_path(self, name):
        pass

    @property
    def path_to_plugin_config(self):
        return self._config_path(self.PLUGIN_CONF)


class AgentConfigurator(Configurator):

    def __init__(self, installer):
        super(AgentConfigurator, self).__init__(installer)

    def _adjust_plugin_config(self, plugin_conf):
        params = self.get_keystone_params("neutron")
        plugin_conf.add("admin_password", params["service_password"])
        plugin_conf.add("admin_user", params["service_user"])
        plugin_conf.add("admin_tenant_name", params["service_tenant"])
        plugin_conf.add("auth_url", params["endpoints"]["admin"]["uri"])
        plugin_conf.add("debug", self.installer.get_bool_option("debug"))
        plugin_conf.add("verbose", self.installer.get_bool_option("verbose"))

    def _config_path(self, name):
        return name


class CorePluginConfigurator(Configurator):

    def __init__(self, installer):
        super(CorePluginConfigurator, self).__init__(installer)

    def _adjust_plugin_config(self, plugin_conf):
        self.setup_rpc(plugin_conf, rpc_backends=MQ_BACKENDS)
        plugin_conf.add_with_section(
            "DATABASE",
            "sql_connection",
            self.fetch_dbdsn())

    def _config_path(self, name):
        return sh.joinpths('plugins', self.core_plugin, name)
