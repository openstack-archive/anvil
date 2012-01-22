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

from optparse import OptionParser, OptionGroup
from optparse import IndentedHelpFormatter

from devstack import constants
from devstack import utils
from devstack import version

HELP_WIDTH = 80


def parse():

    #version
    version_str = "%prog v" + version.version_string()
    help_formatter = IndentedHelpFormatter(width=HELP_WIDTH)
    parser = OptionParser(version=version_str, formatter=help_formatter)

    base_group = OptionGroup(parser, "Install/uninstall/start/stop options")
    known_actions = sorted(constants.ACTIONS)
    actions = "(" + ", ".join(known_actions) + ")"
    base_group.add_option("-a", "--action",
            action="store",
            type="string",
            dest="action",
            metavar="ACTION",
            help="action to perform, ie %s" % (actions))
    base_group.add_option("-d", "--directory",
        action="store",
        type="string",
        dest="dir",
        metavar="DIR",
        help="empty root DIR for install or "\
             "DIR with existing components (ACTION dependent)")
    known_components = sorted(constants.COMPONENT_NAMES)
    components = "(" + ", ".join(known_components) + ")"
    base_group.add_option("-c", "--component",
        action="append",
        dest="component",
        help="openstack component, ie %s" % (components))
    base_group.add_option("-i", "--ignore-deps",
        action="store_false",
        dest="ensure_deps",
        help="ignore dependencies when performing ACTION")
    base_group.add_option("-e", "--ensure-deps",
        action="store_true",
        dest="ensure_deps",
        help="ensure dependencies occur when performing ACTION (default: %default)",
        default=True)
    base_group.add_option("-r", "--ref-component",
        action="append",
        dest="r_component",
        metavar="COMPONENT",
        help="component which will not have ACTION applied but will be referenced as if it was (ACTION dependent)")
    parser.add_option_group(base_group)

    stop_un_group = OptionGroup(parser, "Uninstall/stop options")
    stop_un_group.add_option("-f", "--force",
        action="store_true",
        dest="force",
        help="force ACTION even if no trace found",
        default=False)
    parser.add_option_group(stop_un_group)

    dep_group = OptionGroup(parser, "Dependency options")
    dep_group.add_option("-s", "--list-deps",
        action="store_true",
        dest="list_deps",
        help="show dependencies of COMPONENT (default: %default)",
        default=False)
    parser.add_option_group(dep_group)

    (options, args) = parser.parse_args()

    #extract only what we care about
    output = dict()
    output['components'] = options.component
    output['dir'] = options.dir
    output['ref_components'] = options.r_component
    output['action'] = options.action
    output['list_deps'] = options.list_deps
    output['force'] = options.force
    if(options.ensure_deps):
        output['ignore_deps'] = False
    else:
        output['ignore_deps'] = True
    output['extras'] = args
    return output
