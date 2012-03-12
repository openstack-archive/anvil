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

import tempfile

from optparse import IndentedHelpFormatter
from optparse import OptionParser, OptionGroup

from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import version

HELP_WIDTH = 80
DEF_OS_DIR = "openstack"
LOG = logging.getLogger("devstack.opts")


def _format_list(in_list):
    sorted_list = sorted(in_list)
    return  "[" + ", ".join(sorted_list) + "]"


def parse():

    version_str = "%prog v" + version.version_string()
    help_formatter = IndentedHelpFormatter(width=HELP_WIDTH)
    parser = OptionParser(version=version_str, formatter=help_formatter)
    parser.add_option("-c", "--component",
        action="append",
        dest="component",
        help="openstack component: %s" % (_format_list(settings.COMPONENT_NAMES)))
    parser.add_option("-v", "--verbose",
        action="append_const",
        const=1,
        dest="verbosity",
        default=[1],
        help="increase the verbose level")
    parser.add_option("", "--dryrun",
        action="store_const",
        const=1,
        dest="dryrun",
        default=0,
        help="log actions without actually doing any of them")

    base_group = OptionGroup(parser, "Install & uninstall & start & stop specific options")
    base_group.add_option("-a", "--action",
        action="store",
        type="string",
        dest="action",
        metavar="ACTION",
        help="required action to perform: %s" % (_format_list(settings.ACTIONS)))
    default_dir = sh.joinpths(tempfile.gettempdir(), DEF_OS_DIR)
    base_group.add_option("-d", "--directory",
        action="store",
        type="string",
        dest="dir",
        metavar="DIR",
        default=default_dir,
        help=("empty root DIR for install or "
              "DIR with existing components for start/stop/uninstall "
              "(default: %default)"))
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
        dest="ref_components",
        metavar="COMPONENT",
        help="component which will not have ACTION applied but will be referenced as if it was (ACTION dependent)")
    parser.add_option_group(base_group)

    stop_un_group = OptionGroup(parser, "Uninstall & stop specific options")
    stop_un_group.add_option("-n", "--no-force",
        action="store_true",
        dest="force",
        help="stop the continuation of ACTION if basic errors occur (default: %default)",
        default=False)
    parser.add_option_group(stop_un_group)

    un_group = OptionGroup(parser, "Uninstall specific options")
    un_group.add_option("-k", "--keep-old",
        action="store_true",
        dest="keep_old",
        help="uninstall will keep as much of the old install as it can (default: %default)",
        default=False)
    parser.add_option_group(un_group)

    #extract only what we care about
    (options, args) = parser.parse_args()
    output = dict()
    output['components'] = options.component or list()
    output['dir'] = options.dir or ""
    output['dryrun'] = options.dryrun or False
    output['ref_components'] = options.ref_components or list()
    output['action'] = options.action or ""
    output['force'] = not options.force
    output['ignore_deps'] = not options.ensure_deps
    output['keep_old'] = options.keep_old
    output['extras'] = args
    output['verbosity'] = len(options.verbosity)

    return output
