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

from anvil import utils

# v1 seems correct until bug 1190331 is fixed
# where the cinderclient doesn't seem to know anything
# beyond v1 unless told.
VERSION = "v1"


def get_shared_params(ip, api_host, api_port=8776, protocol='http', **kwargs):
    mp = {}
    mp['service_host'] = ip

    # Uri's of the various cinder endpoints
    mp['endpoints'] = {
        'admin': {
            'uri': utils.make_url(protocol, api_host, api_port, VERSION),
            'port': api_port,
            'host': api_host,
            'protocol': protocol,
        },
    }
    mp['endpoints']['internal'] = dict(mp['endpoints']['admin'])
    mp['endpoints']['public'] = dict(mp['endpoints']['admin'])
    return mp
