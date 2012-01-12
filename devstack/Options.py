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

import optparse
from optparse import OptionParser

import Util

VERSION_ID = "%0.2f" % (Util.VERSION)


def parse():
    versionstr = "%prog v" + VERSION_ID
    parser = OptionParser(version=versionstr)

    known_actions = sorted(set(Util.ACTIONS))
    actions = "(" + ", ".join(known_actions) + ")"
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

    known_components = sorted(set(Util.NAMES))
    components = "(" + ", ".join(known_components) + ")"
    parser.add_option("-c",  "--component",
        action="append",
        dest="component",
        help="stack component, ie %s" % (components))

    (options, args) = parser.parse_args()

    #extract only what we care about
    output = dict()
    output['component'] = options.component
    output['dir'] = options.dir
    output['action'] = options.action
    output['extras'] = args
    return output
