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

from devstack import log as logging
from devstack import settings
from devstack import utils

LOG = logging.getLogger("devstack.progs.deps")
PROG_NAME = "DEPENDENCY LIST"


def log_deps(components):
    shown = set()
    left_show = list(components)
    while(len(left_show) != 0):
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
    return True


def _run_list_deps(args):
    components = settings.parse_components(args.pop("components"), True).keys()
    components = sorted(components)
    components.reverse()
    utils.welcome(PROG_NAME)
    LOG.info("Showing dependencies of [%s]" % (", ".join(sorted(components))))
    return log_deps(components)


def run(args):
    return _run_list_deps(args)
