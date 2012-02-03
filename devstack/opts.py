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

from optparse import IndentedHelpFormatter
from optparse import OptionParser, OptionGroup

from devstack import log as logging
from devstack import settings
from devstack import version

HELP_WIDTH = 80
LOG = logging.getLogger("devstack.opts")


def _format_list(in_list):
    sorted_list = sorted(in_list)
    return  "[" + ", ".join(sorted_list) + "]"


def parse():

    #version
    version_str = "%prog v" + version.version_string()
    help_formatter = IndentedHelpFormatter(width=HELP_WIDTH)
    parser = OptionParser(version=version_str, formatter=help_formatter)
    parser.add_option("-c", "--component",
        action="append",
        dest="component",
        help="openstack component: %s" % (_format_list(settings.COMPONENT_NAMES)))

    base_group = OptionGroup(parser, "Install/uninstall/start/stop options")
    base_group.add_option("-a", "--action",
        action="store",
        type="string",
        dest="action",
        metavar="ACTION",
        help="required action to perform: %s" % (_format_list(settings.ACTIONS)))
    base_group.add_option("-d", "--directory",
        action="store",
        type="string",
        dest="dir",
        metavar="DIR",
        help=("empty root DIR for install or "
              "DIR with existing components for start/stop/uninstall"),
        default='/opt/stack')
    base_group.add_option("-i", "--ignore-deps",
        action="store_false",
        dest="ensure_deps",
        help="ignore dependencies when performing ACTION")
    base_group.add_option("-e", "--ensure-deps",
        action="store_true",
        dest="ensure_deps",
        help="ensure dependencies when performing ACTION (default: %default)",
        default=True)
    base_group.add_option("-r", "--ref-component",
        action="append",
        dest="r_component",
        metavar="COMPONENT",
        help="component which will not have ACTION applied but will be referenced as if it was (ACTION dependent)")
    base_group.add_option("-k", "--keep-packages",
        action="store_true",
        dest="keep_packages",
        help="uninstall will keep any installed packages on the system")
    parser.add_option_group(base_group)

    stop_un_group = OptionGroup(parser, "Uninstall/stop options")
    stop_un_group.add_option("-f", "--force",
        action="store_true",
        dest="force",
        help="force ACTION even if no trace file found (default: %default)",
        default=True)
    parser.add_option_group(stop_un_group)

    #extract only what we care about
    (options, args) = parser.parse_args()
    output = dict()
    output['components'] = options.component
    output['dir'] = options.dir
    output['ref_components'] = options.r_component
    output['action'] = options.action
    output['force'] = options.force
    if options.ensure_deps:
        output['ignore_deps'] = False
    else:
        output['ignore_deps'] = True
    output['keep_packages'] = options.keep_packages
    output['extras'] = args
    return output
