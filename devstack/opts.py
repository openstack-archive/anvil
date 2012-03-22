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

from devstack.progs import actions
from devstack import log as logging
from devstack import version

HELP_WIDTH = 80
LOG = logging.getLogger("devstack.opts")


def _format_list(in_list):
    sorted_list = sorted(in_list)
    return  "[" + ", ".join(sorted_list) + "]"


def parse():

    version_str = "%prog v" + version.version_string()
    help_formatter = IndentedHelpFormatter(width=HELP_WIDTH)
    parser = OptionParser(version=version_str, formatter=help_formatter)

    # Root options
    parser.add_option("-v", "--verbose",
        action="append_const",
        const=1,
        dest="verbosity",
        default=[1],
        help="increase the verbose level")
    parser.add_option("--dryrun",
        action="store_true",
        dest="dryrun",
        default=False,
        help=("perform ACTION but do not actually run any of the commands"
              " that would normally complete ACTION: (default: %default)"))

    # Install/start/stop/uninstall specific options
    base_group = OptionGroup(parser, "Install & uninstall & start & stop specific options")
    base_group.add_option("-p", "--persona",
        action="store",
        type="string",
        dest="persona_fn",
        default='conf/personas/devstack.sh.yaml',
        metavar="FILE",
        help="required persona yaml file to apply (default: %default)")
    base_group.add_option("-a", "--action",
        action="store",
        type="string",
        dest="action",
        metavar="ACTION",
        help="required action to perform: %s" % (_format_list(actions.get_action_names())))
    base_group.add_option("-d", "--directory",
        action="store",
        type="string",
        dest="dir",
        metavar="DIR",
        help=("empty root DIR for install or "
              "DIR with existing components for start/stop/uninstall"))
    base_group.add_option("--no-prompt-passwords",
                          action="store_false",
                          dest="prompt_for_passwords",
                          default=True,
                          help="do not prompt the user for passwords",
                          )
    parser.add_option_group(base_group)

    # Uninstall and stop options
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

    # Extract only what we care about
    (options, args) = parser.parse_args()
    output = dict()
    output['dir'] = options.dir or ""
    output['dryrun'] = options.dryrun or False
    output['action'] = options.action or ""
    output['force'] = not options.force
    output['keep_old'] = options.keep_old
    output['extras'] = args
    output['persona_fn'] = options.persona_fn
    output['verbosity'] = len(options.verbosity)
    output['prompt_for_passwords'] = options.prompt_for_passwords

    return output
