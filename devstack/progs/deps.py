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

#requires http://pypi.python.org/pypi/termcolor
#but the colors make it worth it :-)
from termcolor import colored

from devstack import settings
from devstack import utils

from devstack.progs import common

PROG_NAME = "Dep. Lister"
DEF_ACTION = settings.INSTALL


def _print_deps(component, deps):
    print(" + " + colored(component, "blue", attrs=['bold']))
    if deps:
        for d in sorted(deps):
            print("    |")
            print("    ------> %s" % (d))


def _clean_action(action):
    if not action:
        return DEF_ACTION
    action = action.strip.lower()
    if action not in settings.ACTIONS:
        return DEF_ACTION
    return action


def _run_dep_comps(args, rep, maxlen):
    components = utils.parse_components(args.get("components"))
    if not components:
        components = dict()
        for c in settings.COMPONENT_NAMES:
            components[c] = list()
        header = utils.center_text("Dependencies (defaulted)", rep, maxlen)
    else:
        header = utils.center_text("Dependencies", rep, maxlen)
    print(header)
    action = _clean_action(args.pop("action"))
    msg = "For action %s" % (action)
    print(utils.center_text(msg, rep, maxlen))
    all_deps = common.get_components_deps(action, components)
    for c in sorted(all_deps.keys()):
        _print_deps(c, all_deps.get(c))


def run(args):
    (rep, maxlen) = utils.welcome(PROG_NAME)
    _run_dep_comps(args, rep, maxlen)
    return True
