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

import multiprocessing

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
    base_group.add_option("-t", "--openstack-version",
                          action="store",
                          type="string",
                          dest="version_fn",
                          default=sh.joinpths(settings.VERSION_DIR, 'default.yaml'),
                          metavar="FILE",
                          help="version yaml file to apply (default: %default)")
    base_group.add_option("-a", "--action",
                          action="store",
                          type="string",
                          dest="action",
                          metavar="ACTION",
                          help="required action to perform: %s" % (_format_list(actions.names())))
    base_group.add_option("-j", "--jobs",
                          action="store",
                          type="int",
                          dest="jobs",
                          default=multiprocessing.cpu_count() + 1,
                          metavar="JOBS",
                          help="number of building jobs to run simultaneously (default: %default)")
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

    build_group = OptionGroup(parser, "Build specific options")
    build_group.add_option('-u', "--usr-only",
                           action="store_true",
                           dest="usr_only",
                           default=False,
                           help=("when packaging only store /usr directory"
                                 " (default: %default)"))
    parser.add_option_group(build_group)

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
    values['jobs'] = options.jobs
    values['persona_fn'] = options.persona_fn
    values['version_fn'] = options.version_fn
    values['verbose'] = options.verbose
    values['usr_only'] = options.usr_only
    values['prompt_for_passwords'] = options.prompt_for_passwords
    values['show_amount'] = max(0, options.show_amount)
    values['store_passwords'] = options.store_passwords
    values['keyring_path'] = options.keyring_path
    values['keyring_encrypted'] = options.keyring_encrypted
    return values
