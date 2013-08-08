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

API_CONF = 'cinder.conf'
PASTE_CONF = 'api-paste.ini'
POLICY_CONF = 'policy.json'
CONFIGS = [PASTE_CONF, API_CONF, POLICY_CONF]

MQ_BACKENDS = {
    'qpid': 'cinder.openstack.common.rpc.impl_qpid',
    'rabbit': 'cinder.openstack.common.rpc.impl_kombu',
}


class CinderConfigurator(base.Configurator):

    # This db will be dropped then created
    DB_NAME = 'cinder'

    def __init__(self, installer):
        super(CinderConfigurator, self).__init__(installer, CONFIGS)
        self.config_adjusters = {PASTE_CONF: self._config_adjust_paste,
                                 API_CONF: self._config_adjust_api}
        self.source_configs = {API_CONF: 'cinder.conf.sample'}
        self.config_dir = sh.joinpths(self.installer.get_option('app_dir'),
                                      'etc',
                                      installer.name)

    def _config_adjust_paste(self, config):
        for (k, v) in self._fetch_keystone_params().items():
            config.add_with_section('filter:authtoken', k, v)

    def _config_adjust_api(self, config):
        config.add('log_dir', '/var/log/cinder')
        self.setup_rpc(config, rpc_backends=MQ_BACKENDS)
        # Setup your sql connection
        config.add('sql_connection', self.fetch_dbdsn())
        # Auth will be using keystone
        config.add('auth_strategy', 'keystone')
        # Where our paste config is
        config.add('api_paste_config', self.target_config(PASTE_CONF))

    def _fetch_keystone_params(self):
        params = self.get_keystone_params('cinder')
        return {
            'auth_host': params['endpoints']['admin']['host'],
            'auth_port': params['endpoints']['admin']['port'],
            'auth_protocol': params['endpoints']['admin']['protocol'],

            'auth_uri': params['endpoints']['public']['uri'],
            'admin_tenant_name': params['service_tenant'],
            'admin_user': params['service_user'],
            'admin_password': params['service_password'],

            'service_host': params['endpoints']['internal']['host'],
            'service_port': params['endpoints']['internal']['port'],
            'service_protocol': params['endpoints']['internal']['protocol'],
            'auth_version': 'v2.0'
        }
