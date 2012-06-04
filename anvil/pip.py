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
from anvil import shell as sh
from anvil import packager as pack

LOG = logging.getLogger(__name__)

PIP_UNINSTALL_CMD_OPTS = ['-y', '-q']
PIP_INSTALL_CMD_OPTS = ['-q']


class Packager(pack.Packager):

    def _make_pip_name(self, name, version):
        if version is None:
            return "%s" % (name)
        return "%s==%s" % (name, version)

    def _get_pip_command(self):
        return self.distro.get_command_config('pip')

    def _install(self, pip):
        root_cmd = self._get_pip_command()
        name_full = self._make_pip_name(pip['name'], pip.get('version'))
        real_cmd = [root_cmd] + ['install'] + PIP_INSTALL_CMD_OPTS
        options = pip.get('options')
        if options:
            if not isinstance(options, (list, tuple)):
                options = [options]
            LOG.debug("Using pip options: %s" % (options))
            for opt in options:
                real_cmd.append("%s" % (opt))
        LOG.audit("Installing python package %r using pip command %s" % (name_full, real_cmd))
        real_cmd.append(name_full)
        sh.execute(*real_cmd, run_as_root=True)

    def _remove(self, pip):
        root_cmd = self._get_pip_command()
        # Versions don't seem to matter here...
        name = self._make_pip_name(pip['name'], None)
        LOG.audit("Uninstalling python package %r using pip command %s" % (name, root_cmd))
        cmd = [root_cmd] + ['uninstall'] + PIP_UNINSTALL_CMD_OPTS + [name]
        sh.execute(*cmd, run_as_root=True)
