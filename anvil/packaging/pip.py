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
from anvil.packaging import base
from anvil import shell as sh

from anvil.packaging.helpers import pip_helper


LOG = logging.getLogger(__name__)

PIP_UNINSTALL_CMD_OPTS = ['-y', '-q']
PIP_INSTALL_CMD_OPTS = ['-q']


def extract_requirement(pkg_info):
    return pip_helper.create_requirement(
        pkg_info.get('name', ''), pkg_info.get('version'))


class Packager(base.Packager):
    def __init__(self, distro, remove_default=False):
        super(Packager, self).__init__(distro, remove_default)
        self.helper = pip_helper.Helper(distro)
        self.upgraded = {}

    def _get_pip_command(self):
        return self.distro.get_command_config('pip')

    def _execute_pip(self, cmd):
        pip_cmd = self._get_pip_command()
        if not isinstance(pip_cmd, (list, tuple)):
            pip_cmd = [pip_cmd]
        pip_cmd = pip_cmd + cmd
        try:
            sh.execute(*pip_cmd, run_as_root=True)
        finally:
            # The known packages installed is probably
            # not consistent anymore so uncache it
            self.helper.uncache()

    def _remove(self, pip):
        # Versions don't seem to matter here...
        remove_what = extract_requirement(pip)
        if not self.helper.is_installed(remove_what.name):
            return
        cmd = ['uninstall'] + PIP_UNINSTALL_CMD_OPTS + [remove_what.name]
        self._execute_pip(cmd)
