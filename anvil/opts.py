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
from anvil import cfg_helpers
from anvil import settings
from anvil import shell as sh
from anvil import version

HELP_WIDTH = 80


def _format_list(in_list):
    sorted_list = sorted(in_list)
    return "[" + ", ".join(sorted_list) + "]"


def parse():

    prog_name = settings.PROG_NAME
    version_str = "%s v%s" % (prog_name, version.version_string())
    help_formatter = IndentedHelpFormatter(width=HELP_WIDTH)
    parser = OptionParser(version=version_str, formatter=help_formatter)

    # Root options
    parser.add_option("-v", "--verbose",
        action="append_const",
        const=1,
        dest="verbosity",
        default=[1],
        help="increase the verbose level")
    parser.add_option("-o", "--override",
        action="append",
        dest="cli_overrides",
        metavar="OPTION",
        help=("override configuration values (format SECTION/OPTION/VALUE, note "
                "if section is empty 'DEFAULT' is assumed)"))
    parser.add_option("--dryrun",
        action="store_true",
        dest="dryrun",
        default=False,
        help=("perform ACTION but do not actually run any of the commands"
              " that would normally complete ACTION: (default: %default)"))
    opt_help = "configuration file (will be searched for if not provided)"
    parser.add_option("-c", "--config",
        action="store",
        dest="config_fn",
        type="string",
        metavar="FILE",
        help=opt_help)

    # Install/start/stop/uninstall specific options
    base_group = OptionGroup(parser, "Action specific options")
    def_persona = sh.joinpths(settings.PERSONA_DIR, 'devstack.sh.yaml')
    base_group.add_option("-p", "--persona",
        action="store",
        type="string",
        dest="persona_fn",
        default=def_persona,
        metavar="FILE",
        help="persona yaml file to apply (default: %default)")
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
        help=("empty root DIR or "
              "DIR with existing components"))
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
    output['config_fn'] = options.config_fn
    output['persona_fn'] = options.persona_fn
    output['verbosity'] = len(options.verbosity)
    output['cli_overrides'] = options.cli_overrides or list()
    output['prompt_for_passwords'] = options.prompt_for_passwords

    return output
