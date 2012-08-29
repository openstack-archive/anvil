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

from tempfile import TemporaryFile

from anvil import colorizer
from anvil import components as comp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.components.helpers import rabbit as rhelper

LOG = logging.getLogger(__name__)

# Default password (guest)
RESET_BASE_PW = ''


class RabbitUninstaller(comp.PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgUninstallComponent.__init__(self, *args, **kargs)
        self.runtime = self.siblings.get('running')

    def pre_uninstall(self):
        try:
            LOG.debug("Attempting to reset the rabbit-mq guest password to: %s", colorizer.quote(RESET_BASE_PW))
            self.runtime.start()
            self.runtime.wait_active()
            cmd = self.distro.get_command('rabbit-mq', 'change_password') + [RESET_BASE_PW]
            sh.execute(*cmd, run_as_root=True)
            LOG.info("Restarting so that your rabbit-mq password is reflected.")
            self.runtime.restart()
            self.runtime.wait_active()
        except IOError:
            LOG.warn(("Could not reset the rabbit-mq password. You might have to manually "
                      "reset the password to %s before the next install"), colorizer.quote(RESET_BASE_PW))


class RabbitInstaller(comp.PkgInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgInstallComponent.__init__(self, *args, **kargs)
        self.runtime = self.siblings.get('running')

    def warm_configs(self):
        rhelper.get_shared_passwords(self)

    def _setup_pw(self):
        user_id = self.get_option('user_id')
        LOG.info("Setting up your rabbit-mq %s password.", colorizer.quote(user_id))
        self.runtime.start()
        self.runtime.wait_active()
        cmd = list(self.distro.get_command('rabbit-mq', 'change_password'))
        cmd += [user_id, rhelper.get_shared_passwords(self)['pw']]
        sh.execute(*cmd, run_as_root=True)
        LOG.info("Restarting so that your rabbit-mq password is reflected.")
        self.runtime.restart()
        self.runtime.wait_active()

    def post_install(self):
        comp.PkgInstallComponent.post_install(self)
        self._setup_pw()


class RabbitRuntime(comp.ProgramRuntime):
    def __init__(self, *args, **kargs):
        comp.ProgramRuntime.__init__(self, *args, **kargs)
        self.wait_time = self.get_int_option('service_wait_seconds')

    def start(self):
        if self.status()[0].status != comp.STATUS_STARTED:
            self._run_cmd(self.distro.get_command('rabbit-mq', 'start'))
            return 1
        else:
            return 0

    @property
    def apps_to_start(self):
        return ['rabbit-mq']

    def status(self):
        # This has got to be the worst status output.
        #
        # I have ever seen (its like a weird mix json+crap)
        status_cmd = self.distro.get_command('rabbit-mq', 'status')
        (sysout, stderr) = sh.execute(*status_cmd, check_exit_code=False, run_as_root=True)
        st = comp.STATUS_UNKNOWN
        combined = (sysout + stderr).lower()
        if utils.has_any(combined, 'nodedown', "unable to connect to node", 'unrecognized'):
            st = comp.STATUS_STOPPED
        elif combined.find('running_applications') != -1:
            st = comp.STATUS_STARTED
        return [
            comp.ProgramStatus(status=st,
                               details=(sysout + stderr).strip()),
        ]

    def _run_cmd(self, cmd, check_exit=True):
        # This seems to fix one of the bugs with rabbit mq starting and stopping
        # not cool, possibly connected to the following bugs:
        #
        # See: https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878597
        # See: https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878600
        #
        # RHEL seems to have this bug also...
        with TemporaryFile() as f:
            return sh.execute(*cmd, run_as_root=True,
                        stdout_fh=f, stderr_fh=f,
                        check_exit_code=check_exit)

    def restart(self):
        self._run_cmd(self.distro.get_command('rabbit-mq', 'restart'))
        return 1

    def stop(self):
        if self.status()[0].status != comp.STATUS_STOPPED:
            self._run_cmd(self.distro.get_command('rabbit-mq', 'stop'))
            return 1
        else:
            return 0
