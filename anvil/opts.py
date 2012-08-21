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

from anvil import actions
from anvil import settings
from anvil import shell as sh
from anvil import version


def _format_list(in_list):
    sorted_list = sorted(in_list)
    return "[" + ", ".join(sorted_list) + "]"


def parse():

    version_str = "%s v%s" % ('anvil', version.version_string())
    help_formatter = IndentedHelpFormatter(width=120)
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
              " that would normally complete ACTION)"))

    # Install/start/stop/uninstall specific options
    base_group = OptionGroup(parser, "Action specific options")
    base_group.add_option("-p", "--persona",
        action="store",
        type="string",
        dest="persona_fn",
        default=sh.joinpths(settings.PERSONA_DIR, 'in-a-box', 'basic.yaml'),
        metavar="FILE",
        help="persona yaml file to apply (default: %default)")
    base_group.add_option("-a", "--action",
        action="store",
        type="string",
        dest="action",
        metavar="ACTION",
        help="required action to perform: %s" % (_format_list(actions.names())))
    base_group.add_option("-d", "--directory",
        action="store",
        type="string",
        dest="dir",
        metavar="DIR",
        help=("empty root DIR or "
              "DIR with existing components"))
    base_group.add_option("--no-prompt-passwords",
                          action="store_false",
                          dest="prompt_for_passwords",
                          default=True,
                          help="do not prompt the user for passwords")
    base_group.add_option("--no-store-passwords",
        action="store_false",
        dest="store_passwords",
        default=True,
        help="do not store the users passwords into yaml files")
    parser.add_option_group(base_group)

    status_group = OptionGroup(parser, "Status specific options")
    status_group.add_option('-s', "--show",
        action="store_true",
        dest="show_full",
        help="show details if applicable when showing status",
        default=False)
    parser.add_option_group(status_group)

    # Extract only what we care about, these will be passed
    # to the constructor of actions as arguments 
    # so don't adjust the naming wily nilly...
    (options, args) = parser.parse_args()
    output = {}
    output['dir'] = (options.dir or "")
    output['dryrun'] = (options.dryrun or False)
    output['action'] = (options.action or "")
    output['extras'] = args
    output['persona_fn'] = options.persona_fn
    output['verbosity'] = len(options.verbosity)
    output['prompt_for_passwords'] = options.prompt_for_passwords
    output['show_full'] = options.show_full
    output['store_passwords'] = options.store_passwords

    return output
