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

import optparse
import os
import re
import sys

POSSIBLE_TOPDIR = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))
sys.path.insert(0, POSSIBLE_TOPDIR)

from devstack import settings
from devstack import utils

from devstack.components import db
from devstack.components import glance
from devstack.components import horizon
from devstack.components import keystone
from devstack.components import keystone_client
from devstack.components import nova
from devstack.components import nova_client
from devstack.components import novnc
from devstack.components import quantum
from devstack.components import quantum_client
from devstack.components import rabbit
from devstack.components import swift
from devstack.components import swift_keystone

PROG_NAME = "Describer"

#this determines how descriptions for components are found
_DESCR_MAP = {
    settings.DB: db.describe,
    settings.GLANCE: glance.describe,
    settings.HORIZON: horizon.describe,
    settings.KEYSTONE: keystone.describe,
    settings.KEYSTONE_CLIENT: keystone_client.describe,
    settings.NOVA: nova.describe,
    settings.NOVA_CLIENT: nova_client.describe,
    settings.QUANTUM: quantum.describe,
    settings.RABBIT: rabbit.describe,
    settings.SWIFT: swift.describe,
    settings.SWIFT_KEYSTONE: swift_keystone.describe,
    settings.NOVNC: novnc.describe,
    settings.QUANTUM_CLIENT: quantum_client.describe,
}


def _run_describe_comps(args, rep, maxlen):
    components = utils.parse_components(args.get("components"))
    if not components:
        components = dict()
        for c in settings.COMPONENT_NAMES:
            components[c] = list()
        header = utils.center_text("Descriptions (defaulted)", rep, maxlen)
    else:
        header = utils.center_text("Descriptions", rep, maxlen)
    print(header)
    c_keys = sorted(components.keys())
    for c in c_keys:
        print("Name: " + utils.color_text(c, "blue", True))
        describer = _DESCR_MAP.get(c)
        print(describer(components.get(c)))


def run(args):
    (rep, maxlen) = utils.welcome(PROG_NAME)
    _run_describe_comps(args, rep, maxlen)
    return True


def main():
    parser = optparse.OptionParser()
    known_components = sorted(settings.COMPONENT_NAMES)
    components = "(" + ", ".join(known_components) + ")"
    parser.add_option("-c", "--component",
        action="append",
        dest="component",
        help="openstack component, ie %s" % (components))
    (options, args) = parser.parse_args()
    opts = dict()
    opts['components'] = options.component
    result = run(opts)
    if not result:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
