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

import io
import weakref

from anvil import cfg
from anvil import exceptions
from anvil import shell as sh
from anvil import utils

from anvil.components.helpers import db as dbhelper
from anvil.components.helpers import keystone as khelper


class Configurator(object):
    DB_NAME = "undefined"

    def __init__(self, installer, configs=None):
        self.installer = weakref.proxy(installer)
        self.configs = configs or []
        self.source_configs = {}
        self.config_adjusters = {}
        self.config_dir = None

    @property
    def config_files(self):
        return list(self.configs)

    @property
    def link_dir(self):
        link_dir_base = self.installer.distro.get_command_config('base_link_dir')
        return sh.joinpths(link_dir_base, self.installer.name)

    def config_adjust(self, contents, name):
        adjuster = self.config_adjusters.get(name)
        if adjuster:
            if isinstance(contents, unicode):
                contents = contents.encode("utf-8")
            with io.BytesIO(contents) as stream:
                config = cfg.create_parser(cfg.RewritableConfigParser, self.installer)
                config.readfp(stream)
                adjuster(cfg.DefaultConf(config))
                contents = config.stringify(name)
        return contents

    def replace_config(self, config_fn):
        return config_fn not in self.config_adjusters

    def source_config(self, config_fn):
        if self.config_dir:
            if config_fn in self.source_configs:
                config_fn = self.source_configs.get(config_fn)
            fn = sh.joinpths(self.config_dir, config_fn)
            return (fn, sh.load_file(fn))
        return utils.load_template(self.installer.name, config_fn)

    def config_param_replace(self, config_fn, contents, parameters):
        if self.replace_config(config_fn):
            return utils.expand_template(contents, parameters)
        return contents

    def target_config(self, config_fn):
        return sh.joinpths(self.installer.cfg_dir, config_fn)

    def setup_rpc(self, conf, rpc_backends=None, mq_type=None):
        # How is your message queue setup?
        if not mq_type:
            raw_mq_type = self.installer.get_option('mq-type')
            if raw_mq_type:
                mq_type = utils.canon_mq_type(raw_mq_type)
        if not mq_type:
            msg = ("%s requires a message queue to operate. "
                   "Please specify a 'mq-type' in configuration."
                   % self.installer.name.title())
            raise exceptions.ConfigException(msg)

        if rpc_backends is not None:
            try:
                conf.add('rpc_backend', rpc_backends[mq_type])
            except KeyError:
                msg = ("%s does not support mq type %s."
                       % (self.installer.name.title(), mq_type))
                raise exceptions.ConfigException(msg)

        if mq_type == 'rabbit':
            conf.add('rabbit_host',
                     self.installer.get_option('rabbit', 'host',
                                               default_value=self.installer.get_option('ip')))
            conf.add('rabbit_password', self.installer.get_password('rabbit'))
            conf.add('rabbit_userid', self.installer.get_option('rabbit', 'user_id'))
        elif mq_type == 'qpid':
            conf.add('qpid_hostname',
                     self.installer.get_option('qpid', 'host',
                                               default_value=self.installer.get_option('ip')))
            conf.add('qpid_password', self.installer.get_password('qpid'))
            conf.add('qpid_username', self.installer.get_option('qpid', 'user_id'))

    def fetch_dbdsn(self):
        return dbhelper.fetch_dbdsn(
            dbname=self.DB_NAME,
            utf8=True,
            dbtype=self.installer.get_option('db', 'type'),
            **utils.merge_dicts(self.installer.get_option('db'),
                                dbhelper.get_shared_passwords(self.installer)))

    def get_keystone_params(self, service_user):
        return khelper.get_shared_params(
            ip=self.installer.get_option('ip'),
            service_user=service_user,
            **utils.merge_dicts(self.installer.get_option('keystone'),
                                khelper.get_shared_passwords(self.installer)))

    def setup_db(self):
        dbhelper.drop_db(distro=self.installer.distro,
                         dbtype=self.installer.get_option('db', 'type'),
                         dbname=self.DB_NAME,
                         **utils.merge_dicts(self.installer.get_option('db'),
                                             dbhelper.get_shared_passwords(self.installer)))
        dbhelper.create_db(distro=self.installer.distro,
                           dbtype=self.installer.get_option('db', 'type'),
                           dbname=self.DB_NAME,
                           **utils.merge_dicts(self.installer.get_option('db'),
                                               dbhelper.get_shared_passwords(self.installer)))
