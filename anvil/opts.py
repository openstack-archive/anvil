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

from StringIO import StringIO

import json
import multiprocessing
import textwrap

from optparse import IndentedHelpFormatter
from optparse import OptionGroup
from optparse import OptionParser
from optparse import OptionValueError

from anvil import actions
from anvil import env
from anvil import settings
from anvil import shell as sh
from anvil import utils
from anvil import version

OVERVIEW = """Overview: Anvil is a forging tool to help build OpenStack components
and their dependencies into a complete system. It git checkouts the components and
builds them and their dependencies into packages."""

STEPS = """Steps: For smooth experience please make sure you go through the
following steps when running."""

STEP_SECTIONS = {
    'building': [
        './smithy -a prepare',
        './smithy -a build',
    ],
}


def _format_list(in_list):
    sorted_list = sorted(in_list)
    return "[" + ", ".join(sorted_list) + "]"


def _size_cb(option, opt_str, value, parser):
    try:
        parser.values.show_amount = utils.to_bytes(value)
    except (TypeError, ValueError) as e:
        raise OptionValueError("Invalid value for %s due to %s" % (opt_str, e))


class SmithyHelpFormatter(IndentedHelpFormatter):
    def _wrap_it(self, text):
        return textwrap.fill(text, width=self.width,
                             initial_indent="", subsequent_indent="  ")

    def format_epilog(self, epilog):
        buf = StringIO()
        buf.write(IndentedHelpFormatter.format_epilog(self, epilog))
        buf.write("\n")
        buf.write(self._wrap_it('For further information check out: '
                                'http://anvil.readthedocs.org'))
        buf.write("\n")
        return buf.getvalue()

    def format_usage(self, usage):
        buf = StringIO()
        buf.write(IndentedHelpFormatter.format_usage(self, usage))
        buf.write("\n")
        buf.write(self._wrap_it(OVERVIEW))
        buf.write("\n\n")
        buf.write(self._wrap_it(STEPS))
        buf.write("\n\n")
        for k in sorted(STEP_SECTIONS.keys()):
            buf.write("%s:\n" % (k.title()))
            for line in STEP_SECTIONS[k]:
                buf.write("  %s\n" % (line))
        return buf.getvalue()


def _get_default_dir():
    root_dir = env.get_key('INSTALL_ROOT')
    if root_dir:
        return root_dir
    return sh.joinpths(sh.gethomedir(), 'openstack')


def parse(previous_settings=None):

    version_str = "%s v%s" % ('anvil', version.version_string())
    help_formatter = SmithyHelpFormatter(width=120)
    parser = OptionParser(version=version_str, formatter=help_formatter,
                          prog='smithy')

    # Root options
    parser.add_option("-v", "--verbose",
                      action="store_true",
                      dest="verbose",
                      default=False,
                      help="make the output logging verbose")

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
    base_group.add_option("-o", "--origins",
                          action="store",
                          type="string",
                          dest="origins_fn",
                          default=sh.joinpths(settings.ORIGINS_DIR, 'master.yaml'),
                          metavar="FILE",
                          help="yaml file describing where to get openstack sources "
                               "from (default: %default)")
    base_group.add_option("--origins-patch",
                          action="store",
                          type="string",
                          dest="origins_patch_fn",
                          default=None,
                          metavar="FILE",
                          help="origins file patch, jsonpath format (rfc6902)")
    base_group.add_option("--distros-patch",
                          action="store",
                          type="string",
                          dest="distros_patch_fn",
                          default=None,
                          metavar="FILE",
                          help="distros file patch, jsonpath format (rfc6902)")
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
                          default=_get_default_dir(),
                          help=("empty root DIR or DIR with existing components (default: %default)"))
    base_group.add_option("--tee-file",
                          action="store",
                          type="string",
                          dest="tee_file",
                          metavar="FILE",
                          default='/var/log/anvil.log',
                          help=("location to store tee of output (default: %default)"))
    parser.add_option_group(base_group)

    build_group = OptionGroup(parser, "Build specific options")
    build_group.add_option('-u', "--usr-only",
                           action="store_true",
                           dest="usr_only",
                           default=False,
                           help=("when packaging only store /usr directory"
                                 " (default: %default)"))
    build_group.add_option("--venv-deploy-dir",
                           action="store",
                           type="string",
                           dest="venv_deploy_dir",
                           default=None,
                           help=("for virtualenv builds, make the virtualenv "
                                 "relocatable to a directory different from "
                                 "build directory"))
    build_group.add_option('-c', "--overwrite-configs",
                           action="store_true",
                           dest="overwrite_configs",
                           default=False,
                           help=("When packaging do you want rpm to mark config "
                                 "files with %config or treat them as files and "
                                 "overwrite them each time on rpm install"))
    parser.add_option_group(build_group)

    # Extract only what we care about, these will be passed
    # to the constructor of actions as arguments
    # so don't adjust the naming wily nilly...
    if previous_settings:
        parser.set_defaults(**previous_settings)

    (options, _args) = parser.parse_args()
    values = {}
    values['dir'] = (options.dir or "")
    values['action'] = (options.action or "")
    values['jobs'] = options.jobs
    values['persona_fn'] = options.persona_fn
    values['origins_fn'] = options.origins_fn
    values['verbose'] = options.verbose
    values['usr_only'] = options.usr_only
    values['tee_file'] = options.tee_file
    if options.origins_patch_fn:
        with open(options.origins_patch_fn) as fp:
            values['origins_patch'] = json.load(fp)
    if options.distros_patch_fn:
        with open(options.distros_patch_fn) as fp:
            values['distros_patch'] = json.load(fp)
    values['venv_deploy_dir'] = options.venv_deploy_dir
    return values
