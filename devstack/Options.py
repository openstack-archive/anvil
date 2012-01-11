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

import Util

KNOWN_COMPONENTS = set(Util.NAMES)
KNOWN_ACTIONS = set(Util.ACTIONS)


def parse():
    parser = OptionParser()
    actions = "(" + ", ".join(KNOWN_ACTIONS) + ")"
    parser.add_option("-a", "--action",
            action="store",
            type="string",
            dest="action",
            metavar="ACTION",
            help="action to perform, ie %s" % (actions))

    parser.add_option("-d",  "--directory",
        action="store",
        type="string",
        dest="dir",
        metavar="DIR",
        help="root DIR for new components or DIR with existing components (ACTION dependent)")

    components = "(" + ", ".join(KNOWN_COMPONENTS) + ")"
    parser.add_option("-c",  "--component",
        action="append",
        dest="component",
        help="stack component, ie %s" % (components))

    (options, args) = parser.parse_args()
    output = dict()
    if(options != None):
        output = vars(options)
    return output
