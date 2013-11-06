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

API_CONF = 'ceilometer.conf'
PIPELINE_CONF = 'pipeline.yaml'
SOURCES_CONF = 'sources.json'
POLICY_CONF = 'policy.json'
CONFIGS = [PIPELINE_CONF, API_CONF, POLICY_CONF, SOURCES_CONF]


class CeilometerConfigurator(base.Configurator):
    DB_NAME = 'ceilometer'

    def __init__(self, installer):
        super(CeilometerConfigurator, self).__init__(installer, CONFIGS)
        self.config_adjusters = {
            API_CONF: self._config_adjust_api,
        }
        self.source_configs = {API_CONF: 'ceilometer.conf.sample'}
        self.config_dir = sh.joinpths(self.installer.get_option('app_dir'),
                                      'etc',
                                      installer.name)

    def _config_adjust_api(self, config):
        # Setup your log dir
        config.add('log_dir', '/var/log/ceilometer')
        # Setup your sql connection
        config.add_with_section('database', 'connection', self.fetch_dbdsn())
