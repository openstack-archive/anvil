# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
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

import weakref

from anvil import cfg
from anvil import utils
from anvil import log as logging

from anvil.components.helpers import rabbit as rbhelper
from anvil.components.helpers import db as dbhelper

LOG = logging.getLogger(__name__)

# Special generated conf
API_CONF = 'cinder.conf'

# Paste configuration
PASTE_CONF = 'api-paste.ini'

# Message queue types to there internal 'canonicalized' name
MQ_TYPES = {
    'qpid': 'qpid',
    'qpidd': 'qpid',
    'rabbit': 'rabbit',
    'rabbit-mq': 'rabbit',
}

# This db will be dropped then created
DB_NAME = 'cinder'


def canon_mq_type(mq_type):
    mq_type = str(mq_type).lower().strip()
    return MQ_TYPES.get(mq_type, 'rabbit')


def get_shared_params(ip, api_host, api_port=8776, protocol='http', **kwargs):
    mp = {}
    mp['service_host'] = ip

    # Uri's of the various cinder endpoints
    mp['endpoints'] = {
        'volume': {
            'uri': utils.make_url(protocol, api_host, api_port, "v2"),
            'port': api_port,
            'host': api_host,
            'protocol': protocol,
        },
        'internal': {
        }
    }

    return mp

class ConfConfigurator(object):

    def __init__(self, installer):
        self.installer = weakref.proxy(installer)

    def generate(self, fn):

        backing = cfg.create_parser(cfg.BuiltinConfigParser, self.installer)
        
        # Everything built goes in here
        cinder_conf = cfg.DefaultConf(backing)

        # Used more than once so we calculate it ahead of time
        hostip = self.installer.get_option('ip')

        # How is your message queue setup?
        mq_type = canon_mq_type(self.installer.get_option('mq-type'))
        if mq_type == 'rabbit':
            cinder_conf.add('rabbit_host', self.installer.get_option('rabbit', 'host', default_value=hostip))
            cinder_conf.add('rabbit_password', rbhelper.get_shared_passwords(self.installer)['pw'])
            cinder_conf.add('rabbit_userid', self.installer.get_option('rabbit', 'user_id'))

        # Setup your sql connection
        dbdsn = dbhelper.fetch_dbdsn(
            dbname=DB_NAME,
            utf8=True,
            dbtype=self.installer.get_option('db', 'type'),
            **utils.merge_dicts(self.installer.get_option('db'),
            dbhelper.get_shared_passwords(self.installer)))
        cinder_conf.add('sql_connection', dbdsn)

        # Auth will be using keystone
        cinder_conf.add('auth_strategy', 'keystone')

        # Where our paste config is
        cinder_conf.add('api_paste_config', self.installer.target_config(PASTE_CONF))

        # Extract to finish
        return backing.stringify(fn)

    def _get_content(self, cinder_conf):
        generated_content = cinder_conf.generate()
        return generated_content
