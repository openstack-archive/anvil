# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import re

from devstack import log as logging
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
from devstack.components import openstack_x
from devstack.components import quantum
from devstack.components import rabbit
from devstack.components import swift

LOG = logging.getLogger("devstack.progs.misc")
PROG_NAME = "MISC"

_DESCR_MAP = {
    settings.DB: db.describe,
    settings.GLANCE: glance.describe,
    settings.HORIZON: horizon.describe,
    settings.KEYSTONE: keystone.describe,
    settings.KEYSTONE_CLIENT: keystone_client.describe,
    settings.NOVA: nova.describe,
    settings.NOVA_CLIENT: nova_client.describe,
    settings.OPENSTACK_X: openstack_x.describe,
    settings.QUANTUM: quantum.describe,
    settings.RABBIT: rabbit.describe,
    settings.SWIFT: swift.describe,
    settings.NOVNC: novnc.describe,
}


def log_deps(components):
    shown = set()
    left_show = list(components)
    while left_show:
        c = left_show.pop()
        deps = settings.get_dependencies(c)
        dep_str = ""
        dep_len = len(deps)
        if dep_len >= 1:
            dep_str = "component"
            if dep_len > 1:
                dep_str += "s"
            dep_str += ":"
        elif dep_len == 0:
            dep_str = "no components."
        LOG.info("%s depends on %s" % (c, dep_str))
        for d in deps:
            LOG.info("\t%s" % (d))
        shown.add(c)
        for d in deps:
            if d not in shown and d not in left_show:
                left_show.append(d)


def _run_list_deps(args):
    components = settings.parse_components(args.get("components"), True).keys()
    components = sorted(components)
    components.reverse()
    return log_deps(components)


def _run_describe_comps(args):
    components = settings.parse_components(args.get("components"), True)
    c_keys = sorted(components.keys())
    for c in c_keys:
        LOG.info("Component %s {", c)
        describer = _DESCR_MAP.get(c)
        info = describer(components.get(c))
        if info:
            lines = info.splitlines()
            for line in lines:
                if len(line) == 0:
                    continue
                #do some basic formatting
                mtch = re.match(r"^(\s*)(.*)$", line)
                new_line = line
                if mtch:
                    space_am = len(mtch.group(1)) * 2
                    new_line = " " * space_am + mtch.group(2)
                LOG.info(new_line)
        LOG.info("}")


def run(args):
    prog_name = PROG_NAME
    if args.get('list_deps'):
        prog_name += " [DEPS]"
    if args.get('describe_comp'):
        prog_name += " [DESCRIBE]"
    utils.welcome(prog_name)
    if args.get('list_deps'):
        _run_list_deps(args)
    if args.get('describe_comp'):
        _run_describe_comps(args)
    return True
