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
    quantum_host = cfg.getdefaulted('quantum', 'quantum_host', host_ip)
    quantum_port = cfg.getdefaulted('quantum', 'quantum_port', '9696')
    quantum_proto = cfg.getdefaulted('quantum', 'quantum_protocol', 'http')
    quantum_uri = utils.make_url(quantum_proto, quantum_host, quantum_port)
    mp['endpoints'] = {
        'admin': {
            'uri': quantum_uri,
            'port': quantum_port,
            'protocol': quantum_proto,
            'host': quantum_host,
        },
    }
    mp['endpoints']['public'] = dict(mp['endpoints']['admin'])
    mp['endpoints']['internal'] = dict(mp['endpoints']['public'])

    return mp
