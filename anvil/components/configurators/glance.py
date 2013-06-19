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

from anvil import log as logging
from anvil import shell as sh

from anvil.components.helpers import glance as ghelper

from anvil.components.configurators import base

# Config files/sections
API_CONF = "glance-api.conf"
REG_CONF = "glance-registry.conf"
API_PASTE_CONF = 'glance-api-paste.ini'
REG_PASTE_CONF = 'glance-registry-paste.ini'
LOGGING_CONF = "logging.conf"
POLICY_JSON = 'policy.json'
CONFIGS = [API_CONF, REG_CONF, API_PASTE_CONF,
           REG_PASTE_CONF, POLICY_JSON, LOGGING_CONF]

LOG = logging.getLogger(__name__)


class GlanceConfigurator(base.Configurator):

    # This db will be dropped and created
    DB_NAME = "glance"

    def __init__(self, installer):
        super(GlanceConfigurator, self).__init__(installer, CONFIGS)
        self.config_adjusters = {REG_CONF: self._config_adjust_reg,
                                 API_CONF: self._config_adjust_api,
                                 REG_PASTE_CONF: self._config_adjust_paste,
                                 API_PASTE_CONF: self._config_adjust_paste,
                                 LOGGING_CONF: self._config_adjust_logging}
        self.source_configs = {LOGGING_CONF: 'logging.cnf.sample'}
        self.config_dir = sh.joinpths(self.installer.get_option('app_dir'), 'etc')
        self.img_dir = "/var/lib/glance/images"

    def _config_adjust_paste(self, config):
        for (k, v) in self._fetch_keystone_params().items():
            config.add_with_section('filter:authtoken', k, v)

    def _config_adjust_api_reg(self, config):
        config.add('debug', self.installer.get_bool_option('verbose'))
        config.add('verbose', self.installer.get_bool_option('verbose'))
        config.add('sql_connection', self.fetch_dbdsn())
        config.add_with_section('paste_deploy', 'flavor', self.installer.get_option('paste_flavor'))
        for (k, v) in self._fetch_keystone_params().items():
            config.add_with_section('keystone_authtoken', k, v)

    def _config_adjust_api(self, config):
        self._config_adjust_api_reg(config)
        gparams = ghelper.get_shared_params(**self.installer.options)
        config.add('bind_port', gparams['endpoints']['public']['port'])

        def ensure_image_storage(img_store_dir):
            if sh.isdir(img_store_dir):
                return
            LOG.debug("Ensuring file system store directory %r exists.",
                      img_store_dir)
            sh.mkdirslist(img_store_dir,
                          tracewriter=self.installer.tracewriter)

        config.add('default_store', 'file')
        config.add('filesystem_store_datadir', self.img_dir)
        ensure_image_storage(self.img_dir)

    def _config_adjust_reg(self, config):
        self._config_adjust_api_reg(config)
        gparams = ghelper.get_shared_params(**self.installer.options)
        config.add('bind_port', gparams['endpoints']['registry']['port'])

    def _config_adjust_logging(self, config):
        config.add_with_section('logger_root', 'level', 'DEBUG')
        config.add_with_section('logger_root', 'handlers', "devel,production")

    def _fetch_keystone_params(self):
        params = self.get_keystone_params('glance')
        return {
            'auth_host': params['endpoints']['admin']['host'],
            'auth_port': params['endpoints']['admin']['port'],
            'auth_protocol': params['endpoints']['admin']['protocol'],
            'auth_uri': params['endpoints']['public']['uri'],
            'admin_tenant_name': params['service_tenant'],
            'admin_user': params['service_user'],
            'admin_password': params['service_password'],
        }
