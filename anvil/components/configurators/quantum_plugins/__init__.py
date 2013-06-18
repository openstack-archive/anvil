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

from anvil import shell as sh

from anvil.components.configurators import base


class Configurator(base.Configurator):

    DB_NAME = "quantum"
    PLUGIN_CLASS = "quantum.plugins.UNKNOWN"

    def __init__(self, installer, configs, adjusters):
        self.core_plugin = installer.get_option("core_plugin")
        super(Configurator, self).__init__(
            installer,
            ["plugins/%s/%s" % (self.core_plugin, name) for name in configs])
        self.config_adjusters = dict(
            ("plugins/%s/%s" % (self.core_plugin, key), value)
            for key, value in adjusters.iteritems())

    @property
    def config_files(self):
        return list(self.configs)
