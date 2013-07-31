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
from anvil import utils

from anvil.components.helpers import keystone as khelper

from anvil.components.configurators import base

# Configuration files keystone expects...
ROOT_CONF = "keystone.conf"
LOGGING_CONF = "logging.conf"
POLICY_JSON = 'policy.json'
PASTE_CONFIG = 'keystone-paste.ini'
CONFIGS = [ROOT_CONF, LOGGING_CONF, POLICY_JSON, PASTE_CONFIG]

# PKI base files
PKI_FILES = {
    'ca_certs': 'ssl/certs/ca.pem',
    'keyfile': 'ssl/private/signing_key.pem',
    'certfile': 'ssl/certs/signing_cert.pem',
}


class KeystoneConfigurator(base.Configurator):

    # This db will be dropped then created
    DB_NAME = "keystone"

    def __init__(self, installer):
        super(KeystoneConfigurator, self).__init__(installer, CONFIGS)
        self.config_adjusters = {ROOT_CONF: self._config_adjust_root,
                                 LOGGING_CONF: self._config_adjust_logging}
        self.source_configs = {LOGGING_CONF: 'logging.conf.sample',
                               ROOT_CONF: 'keystone.conf.sample',
                               PASTE_CONFIG: PASTE_CONFIG}
        self.config_dir = sh.joinpths(self.installer.get_option('app_dir'), 'etc')

    def _config_adjust_logging(self, config):
        config.add_with_section('logger_root', 'level', 'DEBUG')
        config.add_with_section('logger_root', 'handlers', "devel,production")

    def _config_adjust_root(self, config):
        config.add('log_dir', '/var/log/keystone')
        config.add('log_file', 'keystone-all.log')
        params = khelper.get_shared_params(**utils.merge_dicts(self.installer.options,
                                                               khelper.get_shared_passwords(self.installer)))
        config.add('admin_token', params['service_token'])
        config.add('admin_port', params['endpoints']['admin']['port'])
        config.add('public_port', params['endpoints']['public']['port'])
        config.add('verbose', True)
        config.add('debug', True)
        if self.installer.get_bool_option('enable-pki'):
            config.add_with_section('signing', 'token_format', 'PKI')
            for (k, v) in PKI_FILES.items():
                path = sh.joinpths(self.link_dir, v)
                config.add_with_section('signing', k, path)
        else:
            config.add_with_section('signing', 'token_format', 'UUID')
        config.add_with_section('catalog', 'driver', 'keystone.catalog.backends.sql.Catalog')
        config.remove('DEFAULT', 'log_config')
        config.add_with_section('sql', 'connection', self.fetch_dbdsn())
        config.add_with_section('ec2', 'driver', "keystone.contrib.ec2.backends.sql.Ec2")
