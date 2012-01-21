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

from optparse import OptionParser
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

    #non-boolean options
    known_actions = sorted(constants.ACTIONS)
    actions = "(" + ", ".join(known_actions) + ")"
    parser.add_option("-a", "--action",
            action="store",
            type="string",
            dest="action",
            metavar="ACTION",
            help="action to perform, ie %s" % (actions))

    parser.add_option("-d", "--directory",
        action="store",
        type="string",
        dest="dir",
        metavar="DIR",
        help="root DIR for new components or "\
             "DIR with existing components (ACTION dependent)")

    known_components = sorted(constants.COMPONENT_NAMES)
    components = "(" + ", ".join(known_components) + ")"
    parser.add_option("-c", "--component",
        action="append",
        dest="component",
        help="stack component, ie %s" % (components))

    #boolean options
    parser.add_option("-f", "--force",
        action="store_true",
        dest="force",
        help="force ACTION even if no trace found (ACTION dependent)",
        default=False)

    parser.add_option("-i", "--ignoredeps",
        action="store_true",
        dest="ignore_deps",
        help="ignore dependencies when performing ACTION")

    parser.add_option("-e", "--ensuredeps",
        action="store_false",
        dest="ignore_deps",
        help="ensure dependencies occur when performing ACTION (the default)",
        default=False)

    parser.add_option("-s", "--listdeps",
        action="store_true",
        dest="list_deps",
        help="show dependencies of COMPONENT",
        default=False)

    (options, args) = parser.parse_args()

    #extract only what we care about
    output = dict()
    output['components'] = options.component
    output['dir'] = options.dir
    output['action'] = options.action
    output['list_deps'] = options.list_deps
    output['force'] = options.force
    output['ignore_deps'] = options.ignore_deps
    output['extras'] = args
    return output
