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

from anvil.components import base_install as binstall
from anvil.components import base_runtime as bruntime

LOG = logging.getLogger(__name__)
NO_DELETE = ['guest']


class QpidUninstaller(binstall.PkgUninstallComponent):
    def post_uninstall(self):
        binstall.PkgUninstallComponent.post_uninstall(self)
        user_name = self.get_option('user_id')
        if user_name in NO_DELETE:
            return
        try:
            LOG.debug("Attempting to delete the qpid user/password.")
            cmd = self.distro.get_command('qpid', 'delete_user')
            if cmd:
                cmd.extend([user_name])
                sh.execute(cmd)
        except IOError:
            LOG.warn(("Could not delete the user/password. You might have to manually "
                      "reset the user/password before the next install."))


class QpidInstaller(binstall.PkgInstallComponent):
    def post_install(self):
        binstall.PkgInstallComponent.post_install(self)
        try:
            LOG.debug("Attempting to create the qpid user/password.")
            cmd = self.distro.get_command('qpid', 'create_user')
            if cmd:
                cmd.extend([self.get_option('user_id')])
                sh.execute(cmd, process_input=self.get_password('qpid'))
        except IOError:
            LOG.warn(("Could not create the user/password. You might have to manually "
                      "create the user/password before running."))


class QpidRuntime(bruntime.ServiceRuntime):
    @property
    def applications(self):
        return [self.distro.get_command('qpid', "daemon")[0]]
