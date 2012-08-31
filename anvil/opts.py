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
from optparse import (OptionParser, OptionGroup, OptionValueError)

from anvil import actions
from anvil import settings
from anvil import shell as sh
from anvil import utils
from anvil import version


def _format_list(in_list):
    sorted_list = sorted(in_list)
    return "[" + ", ".join(sorted_list) + "]"


def _size_cb(option, opt_str, value, parser):
    try:
        parser.values.show_amount = utils.to_bytes(value)
    except (TypeError, ValueError) as e:
        raise OptionValueError("Invalid value for %s due to %s" % (opt_str, e))
        

def parse(previous_settings=None):

    version_str = "%s v%s" % ('anvil', version.version_string())
    help_formatter = IndentedHelpFormatter(width=120)
    parser = OptionParser(version=version_str, formatter=help_formatter,
                          prog='smithy')

    # Root options
    parser.add_option("-v", "--verbose",
                      action="store_true",
                      dest="verbose",
                      default=False,
                      help="make the output logging verbose")
    parser.add_option("--dryrun",
                      action="store_true",
                      dest="dryrun",
                      default=False,
                      help=("perform ACTION but do not actually run any of the commands"
                            " that would normally complete ACTION"))
    parser.add_option('-k', "--keyring",
                      action="store",
                      dest="keyring_path",
                      default="/etc/anvil/passwords.cfg",
                      help=("read and create passwords using this keyring file (default: %default)"))
    parser.add_option('-e', "--encrypt",
                      action="store_true",
                      dest="keyring_encrypted",
                      default=False,
                      help=("use a encrypted keyring file (default: %default)"))
    parser.add_option("--no-prompt-passwords",
                      action="store_false",
                      dest="prompt_for_passwords",
                      default=True,
                      help="do not prompt the user for passwords")
    parser.add_option("--no-store-passwords",
                      action="store_false",
                      dest="store_passwords",
                      default=True,
                      help="do not save the users passwords into the users keyring")

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
                          help=("empty root DIR or DIR with existing components"))
    parser.add_option_group(base_group)

    suffixes = ("Known suffixes 'K' (kilobyte, 1024),"
                " 'M' (megabyte, 1024k), 'G' (gigabyte, 1024M)"
                " are supported, 'B' is the default and is ignored")
    status_group = OptionGroup(parser, "Status specific options")
    status_group.add_option('-s', "--show",
                            action="callback",
                            dest="show_amount",
                            type='string',
                            metavar="SIZE",
                            callback=_size_cb,
                            help="show SIZE 'details' when showing component status. " + suffixes)
    parser.add_option_group(status_group)

    pkg_group = OptionGroup(parser, "Packaging specific options")
    pkg_group.add_option('-m', "--match-installed",
                         action="store_true",
                         dest="match_installed",
                         default=False,
                         help=("when packaging attempt to use the versions that are "
                               "installed for the components dependencies"))
    parser.add_option_group(pkg_group)

    uninstall_group = OptionGroup(parser, "Uninstall specific options")
    uninstall_group.add_option("--purge",
                                action="store_true",
                                dest="purge_packages",
                                default=False,
                                help=("assume when a package is not marked as"
                                      " removable that it can be removed (default: %default)"))
    parser.add_option_group(uninstall_group)

    # Extract only what we care about, these will be passed
    # to the constructor of actions as arguments 
    # so don't adjust the naming wily nilly...
    if previous_settings:
        parser.set_defaults(**previous_settings)

    (options, _args) = parser.parse_args()
    values = {}
    values['dir'] = (options.dir or "")
    values['dryrun'] = (options.dryrun or False)
    values['action'] = (options.action or "")
    values['persona_fn'] = options.persona_fn
    values['verbose'] = options.verbose
    values['prompt_for_passwords'] = options.prompt_for_passwords
    values['show_amount'] = max(0, options.show_amount)
    values['store_passwords'] = options.store_passwords
    values['match_installed'] = options.match_installed
    values['purge_packages'] = options.purge_packages
    values['keyring_path'] = options.keyring_path
    values['keyring_encrypted'] = options.keyring_encrypted
    return values
