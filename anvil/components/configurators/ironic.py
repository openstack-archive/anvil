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

API_CONF = 'ironic.conf'
PASTE_CONF = 'api-paste.ini'
POLICY_CONF = 'policy.json'
CONFIGS = [API_CONF, PASTE_CONF, POLICY_CONF]


class IronicConfigurator(base.Configurator):
    DB_NAME = 'ironic'

    def __init__(self, installer):
        super(IronicConfigurator, self).__init__(installer, CONFIGS)
        self.config_adjusters = {}
        self.source_configs = {API_CONF: 'ironic.conf.sample'}
        self.config_dir = sh.joinpths(self.installer.get_option('app_dir'),
                                      'etc',
                                      installer.name)
