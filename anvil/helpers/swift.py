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


from anvil import log
from anvil import utils

LOG = log.getLogger(__name__)


def get_shared_params(cfg):
    mp = dict()

    host_ip = cfg.get('host', 'ip')
    mp['service_host'] = host_ip

    # Components of the various endpoints
    swift_host = cfg.getdefaulted('swift', 'swift_host', host_ip)
    swift_port = cfg.getdefaulted('swift', 'swift_port', '8080')
    swift_proto = cfg.getdefaulted('swift', 'swift_protocol', 'http')
    swift_uri = utils.make_url(swift_proto, swift_host, swift_port)
    mp['endpoints'] = {
        'admin': {
            'uri': swift_uri,
            'port': swift_port,
            'protocol': swift_proto,
            'host': swift_host,
        },
    }
    mp['endpoints']['public'] = dict(mp['endpoints']['admin'])
    mp['endpoints']['internal'] = dict(mp['endpoints']['public'])

    return mp
