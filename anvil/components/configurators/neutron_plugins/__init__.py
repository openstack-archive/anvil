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

from anvil.components.configurators import base
from anvil import shell as sh


class Configurator(base.Configurator):

    DB_NAME = "neutron"
    PLUGIN_CLASS = "neutron.plugins.UNKNOWN"

    def __init__(self, installer, configs, adjusters):
        super(Configurator, self).__init__(installer, configs)
        self.config_adjusters = adjusters

    def _config_path(self, name):
        return sh.joinpths('plugins', self.core_plugin, name)


class CorePluginConfigurator(Configurator):

    def __init__(self, installer, configs, adjusters):
        self.core_plugin = installer.get_option("core_plugin")
        super(CorePluginConfigurator, self).__init__(
            installer,
            [self._config_path(name) for name in configs],
            dict((self._config_path(name), value)
                 for key, value in adjusters.iteritems()))

    @property
    def path_to_plugin_config(self):
        raise NotImplementedError()
