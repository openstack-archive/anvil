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

from anvil import log as logging
from anvil import packager as pack
from anvil import shell as sh
from anvil import utils

from anvil.packaging.helpers import pip_helper

LOG = logging.getLogger(__name__)

PIP_UNINSTALL_CMD_OPTS = ['-y', '-q']
PIP_INSTALL_CMD_OPTS = ['-q']
NAMED_VERSION_TEMPL = "%s == %s"


class Packager(pack.Packager):

    def _make_pip_name(self, name, version):
        if not version:
            return str(name)
        else:
            return NAMED_VERSION_TEMPL % (name, version)

    def _get_pip_command(self):
        return self.distro.get_command_config('pip')

    def _compare_against_installed(self, pkg):
        name = pkg['name']
        version = pkg.get('version')
        # Anything with options always gets installed
        options = pkg.get('options')
        if options:
            return pack.DO_INSTALL
        if pip_helper.is_adequate_installed(name, version):
            return pack.ADEQUATE_INSTALLED
        else:
            return pack.DO_INSTALL

    def _execute_pip(self, cmd):
        pip_cmd = self._get_pip_command()
        if not isinstance(pip_cmd, (list, tuple)):
            pip_cmd = [pip_cmd]
        pip_cmd = pip_cmd + cmd
        try:
            sh.execute(*pip_cmd, run_as_root=True)
        finally:
            # The known packages installed is probably not consistent anymore so uncache it
            pip_helper.uncache()

    def _install(self, pip):
        cmd = ['install'] + PIP_INSTALL_CMD_OPTS
        options = pip.get('options')
        if options:
            if not isinstance(options, (list, tuple, set)):
                options = [str(options)]
            for opt in options:
                cmd.append(str(opt))
        cmd.append(self._make_pip_name(pip['name'], pip.get('version')))
        self._execute_pip(cmd)

    def _remove(self, pip):
        # Versions don't seem to matter here...
        name = self._make_pip_name(pip['name'], None)
        if not pip_helper.is_installed(name):
            return pack.NOT_EXISTENT
        cmd = ['uninstall'] + PIP_UNINSTALL_CMD_OPTS + [name]
        self._execute_pip(cmd)
        return pack.REMOVED_OK
