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

from anvil import importer
from anvil import shell as sh

from anvil.components.configurators import base
from anvil.components.configurators.quantum_plugins import dhcp
from anvil.components.configurators.quantum_plugins import l3

# Special generated conf
API_CONF = "quantum.conf"

# Config files/sections
PASTE_CONF = "api-paste.ini"

CONFIGS = [PASTE_CONF, API_CONF]


class QuantumConfigurator(base.Configurator):

    # This db will be dropped and created
    DB_NAME = "quantum"

    def __init__(self, installer):
        super(QuantumConfigurator, self).__init__(installer, CONFIGS)
        self.core_plugin = installer.get_option("core_plugin")
        self.plugin_configurators = {
            'core_plugin': importer.import_entry_point(
                "anvil.components.configurators.quantum_plugins.%s:%sConfigurator" %
                (self.core_plugin, self.core_plugin.title()))(installer),
            'l3': l3.L3Configurator(installer),
            'dhcp': dhcp.DhcpConfigurator(installer),
        }

        self.config_adjusters = {
            PASTE_CONF: self._config_adjust_paste,
            API_CONF: self._config_adjust_api,
        }
        for plugin_configurator in self.plugin_configurators.values():
            self.config_adjusters.update(plugin_configurator.config_adjusters)

    @property
    def config_files(self):
        config_files = list(CONFIGS)
        for plugin_configurator in self.plugin_configurators.values():
            config_files.extend(plugin_configurator.config_files)
        return config_files

    def source_config(self, config_fn):
        if (config_fn.startswith("plugins") or
                config_fn.startswith("rootwrap.d")):
            real_fn = "quantum/%s" % config_fn
        else:
            real_fn = config_fn
        fn = sh.joinpths(self.installer.get_option("app_dir"), "etc", real_fn)
        return (fn, sh.load_file(fn))

    def _config_adjust_paste(self, config):
        config.current_section = "filter:authtoken"
        for (k, v) in self._fetch_keystone_params().items():
            config.add(k, v)

    def _config_adjust_api(self, config):
        config.add("core_plugin", self.plugin_configurators['core_plugin'].PLUGIN_CLASS)
        config.add('auth_strategy', 'keystone')
        config.add("api_paste_config", self.target_config(PASTE_CONF))
        # TODO(aababilov): add debug to other services conf files
        config.add('debug', self.installer.get_bool_option("debug"))
        config.add("log_file", "quantum-server.log")
        config.add("log_dir", "/var/log/quantum")

        # Setup the interprocess locking directory
        # (don't put me on shared storage)
        lock_path = self.installer.get_option('lock_path')
        if not lock_path:
            lock_path = sh.joinpths(self.installer.get_option('component_dir'), 'locks')
        sh.mkdirslist(lock_path, tracewriter=self.installer.tracewriter)
        config.add('lock_path', lock_path)

        self.setup_rpc(config, 'quantum.openstack.common.rpc.impl_kombu')

        config.current_section = "AGENT"
        config.add("root_helper", "sudo quantum-rootwrap /etc/quantum/rootwrap.conf")

        config.current_section = "keystone_authtoken"
        for (k, v) in self._fetch_keystone_params().items():
            config.add(k, v)

    def _fetch_keystone_params(self):
        params = self.get_keystone_params('quantum')
        return {
            "auth_host": params["endpoints"]["admin"]["host"],
            "auth_port": params["endpoints"]["admin"]["port"],
            "auth_protocol": params["endpoints"]["admin"]["protocol"],
            # This uses the public uri not the admin one...
            "auth_uri": params["endpoints"]["admin"]["uri"],
            "admin_tenant_name": params["service_tenant"],
            "admin_user": params["service_user"],
            "admin_password": params["service_password"],
        }

    @property
    def get_path_to_core_plugin_config(self):
        return self.plugin_configurators['core_plugin'].get_plugin_config_file_path
