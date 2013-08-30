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
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.components import base_install as binstall
from anvil.components import base_runtime as bruntime

from anvil.components.helpers import rabbit as rhelper

LOG = logging.getLogger(__name__)

# Default password (guest)
RESET_BASE_PW = ''


class RabbitUninstaller(binstall.PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        binstall.PkgUninstallComponent.__init__(self, *args, **kargs)
        self.runtime = self.siblings.get('running')

    def pre_uninstall(self):
        try:
            LOG.debug("Attempting to reset the rabbit-mq guest password to: %s", colorizer.quote(RESET_BASE_PW))
            self.runtime.start()
            self.runtime.wait_active()
            cmd = self.distro.get_command('rabbit-mq', 'change_password') + [RESET_BASE_PW]
            sh.execute(cmd)
            LOG.info("Restarting so that your rabbit-mq password is reflected.")
            self.runtime.restart()
            self.runtime.wait_active()
        except IOError:
            LOG.warn(("Could not reset the rabbit-mq password. You might have to manually "
                      "reset the password to %s before the next install"), colorizer.quote(RESET_BASE_PW))


class RabbitInstaller(binstall.PkgInstallComponent):
    def __init__(self, *args, **kargs):
        binstall.PkgInstallComponent.__init__(self, *args, **kargs)
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
        sh.execute(cmd)
        LOG.info("Restarting so that your rabbit-mq password is reflected.")
        self.runtime.restart()
        self.runtime.wait_active()

    def post_install(self):
        binstall.PkgInstallComponent.post_install(self)
        self._setup_pw()


class RabbitRuntime(bruntime.ProgramRuntime):
    def start(self):

        def is_active():
            status = self.statii()[0].status
            if status == bruntime.STATUS_STARTED:
                return True
            return False

        if is_active():
            return 1

        self._run_action('start')
        for sleep_secs in utils.ExponentialBackoff():
            LOG.info("Sleeping for %s seconds, rabbit-mq is still not active.",
                     sleep_secs)
            sh.sleep(sleep_secs)
            if is_active():
                return 1
        raise RuntimeError('Failed to start rabbit-mq')

    @property
    def applications(self):
        return [
            bruntime.Program('rabbit-mq'),
        ]

    def statii(self):
        # This has got to be the worst status output.
        #
        # I have ever seen (its like a weird mix json+crap)
        (sysout, stderr) = self._run_action('status', check_exit_code=False)
        st = bruntime.STATUS_UNKNOWN
        combined = (sysout + stderr).lower()
        if utils.has_any(combined, 'nodedown', "unable to connect to node", 'unrecognized'):
            st = bruntime.STATUS_STOPPED
        elif combined.find('running_applications') != -1:
            st = bruntime.STATUS_STARTED
        return [
            bruntime.ProgramStatus(status=st,
                               details={
                                   'STDOUT': sysout,
                                   'STDERR': stderr,
                               }),
        ]

    def _run_action(self, action, check_exit_code=True):
        cmd = self.distro.get_command('rabbit-mq', action)
        if not cmd:
            raise NotImplementedError("No distro command provided to perform action %r" % (action))
        # This seems to fix one of the bugs with rabbit mq starting and stopping
        # not cool, possibly connected to the following bugs:
        #
        # See: https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878597
        # See: https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878600
        #
        # RHEL seems to have this bug also...
        with TemporaryFile() as s_fh:
            with TemporaryFile() as e_fh:
                sh.execute(cmd,
                           stdout_fh=s_fh, stderr_fh=e_fh,
                           check_exit_code=check_exit_code)
                # Read from the file handles instead of the typical output...
                for a_fh in [s_fh, e_fh]:
                    a_fh.flush()
                    a_fh.seek(0)
                return (s_fh.read(), e_fh.read())

    def restart(self):
        self._run_action('restart')
        return 1

    def stop(self):
        if self.statii()[0].status != bruntime.STATUS_STOPPED:
            self._run_action('stop')
            return 1
        else:
            return 0
