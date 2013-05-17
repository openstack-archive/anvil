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

from anvil import exceptions as excp
from anvil import log as logging
from anvil import packager as pack
from anvil import shell as sh

from anvil.packaging.helpers import pip_helper


LOG = logging.getLogger(__name__)

PIP_UNINSTALL_CMD_OPTS = ['-y', '-q']
PIP_INSTALL_CMD_OPTS = ['-q']


def extract_requirement(pkg_info):
    return pip_helper.create_requirement(
        pkg_info.get('name', ''), pkg_info.get('version'))


class Packager(pack.Packager):
    def __init__(self, distro, remove_default=False):
        pack.Packager.__init__(self, distro, remove_default)
        self.helper = pip_helper.Helper(distro)
        self.upgraded = {}

    def _get_pip_command(self):
        return self.distro.get_command_config('pip')

    def _anything_there(self, pip):
        wanted_pip = extract_requirement(pip)
        pip_there = self.helper.get_installed(wanted_pip.key)
        if not pip_there:
            # Nothing installed
            return None
        # Check if version wanted will work with whats installed
        if pip_there.specs[0][1] not in wanted_pip:
            is_upgrading = False
            for o in ['-U', '--upgrade']:
                if o in pip.get('options', []):
                    is_upgrading = True
            if is_upgrading and (wanted_pip.key not in self.upgraded):
                # Upgrade should hopefully get that package to the right version....
                LOG.warn("Upgrade is occuring for %s, even though %s is installed.",
                         wanted_pip, pip_there)
                # Mark it so that we don't keep on flip-flopping on upgrading this
                # package (ie install new, install old, install new....)
                self.upgraded[wanted_pip.key] = wanted_pip
                return None
            else:
                msg = ("Pip %s is already installed"
                       " and it is not compatible with desired"
                       " pip %s")
                msg = msg % (pip_there, wanted_pip)
                raise excp.DependencyException(msg)
        return pip_there

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

    def _install(self, pip):
        cmd = ['install'] + PIP_INSTALL_CMD_OPTS
        options = pip.get('options')
        if options:
            if not isinstance(options, (list, tuple, set)):
                options = [str(options)]
            for opt in options:
                cmd.append(str(opt))
        install_what = extract_requirement(pip)
        cmd.append(str(install_what))
        self._execute_pip(cmd)

    def _remove(self, pip):
        # Versions don't seem to matter here...
        remove_what = extract_requirement(pip)
        if not self.helper.is_installed(remove_what.name):
            return
        cmd = ['uninstall'] + PIP_UNINSTALL_CMD_OPTS + [remove_what.name]
        self._execute_pip(cmd)
