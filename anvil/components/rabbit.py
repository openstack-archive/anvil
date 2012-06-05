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
from anvil import component as comp
from anvil import constants
from anvil import log as logging
from anvil import shell as sh

from anvil.helpers import rabbit as rhelper

LOG = logging.getLogger(__name__)

# Default password (guest)
RESET_BASE_PW = ''

# Config keys we warm up so u won't be prompted later
WARMUP_PWS = ['rabbit']

# Copies from helpers
PW_USER_PROMPT = rhelper.PW_USER_PROMPT


class RabbitUninstaller(comp.PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgUninstallComponent.__init__(self, *args, **kargs)
        runtime_cls = self.siblings.get('running')
        if not runtime_cls:
            self.runtime = RabbitRuntime(*args, **kargs)
        else:
            self.runtime = runtime_cls(*args, **kargs)

    def pre_uninstall(self):
        try:
            self.runtime.restart()
            LOG.info("Attempting to reset the rabbit-mq guest password to: %s", colorizer.quote(RESET_BASE_PW))
            cmd = self.distro.get_command('rabbit-mq', 'change_password') + [RESET_BASE_PW]
            sh.execute(*cmd, run_as_root=True)
        except IOError:
            LOG.warn(("Could not reset the rabbit-mq password. You might have to manually "
                      "reset the password to %s before the next install"), colorizer.quote(RESET_BASE_PW))


class RabbitInstaller(comp.PkgInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgInstallComponent.__init__(self, *args, **kargs)
        runtime_cls = self.siblings.get('running')
        if not runtime_cls:
            self.runtime = RabbitRuntime(*args, **kargs)
        else:
            self.runtime = runtime_cls(*args, **kargs)

    def warm_configs(self):
        for pw_key in WARMUP_PWS:
            self.cfg.get_password(pw_key, PW_USER_PROMPT)

    def _setup_pw(self):
        LOG.info("Setting up your rabbit-mq guest password.")
        self.runtime.restart()
        passwd = self.cfg.get_password("rabbit", PW_USER_PROMPT)
        cmd = self.distro.get_command('rabbit-mq', 'change_password') + [passwd]
        sh.execute(*cmd, run_as_root=True)
        LOG.info("Restarting so that your rabbit-mq guest password is reflected.")
        self.runtime.restart()

    def post_install(self):
        comp.PkgInstallComponent.post_install(self)
        self._setup_pw()


class RabbitRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, *args, **kargs)
        self.wait_time = max(self.cfg.getint('DEFAULT', 'service_wait_seconds'), 1)

    def start(self):
        if self._status() != constants.STATUS_STARTED:
            self._run_cmd(self.distro.get_command('rabbit-mq', 'start'))
            return 1
        else:
            return 0

    def _status(self):
        # This has got to be the worst status output.
        #
        # I have ever seen (its like a weird mix json+crap)
        status_cmd = self.distro.get_command('rabbit-mq', 'status')
        (sysout, stderr) = sh.execute(*status_cmd, check_exit_code=False, run_as_root=True)
        combined = (str(sysout) + str(stderr)).lower()
        if combined.find('nodedown') != -1 or \
           combined.find("unable to connect to node") != -1 or \
           combined.find('unrecognized') != -1:
            return constants.STATUS_STOPPED
        elif combined.find('running_applications') != -1:
            return constants.STATUS_STARTED
        else:
            return constants.STATUS_UNKNOWN

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
        LOG.info("Restarting rabbit-mq.")
        self._run_cmd(self.distro.get_command('rabbit-mq', 'restart'))
        LOG.info("Please wait %s seconds while it starts up." % (self.wait_time))
        sh.sleep(self.wait_time)
        return 1

    def stop(self):
        if self._status() != constants.STATUS_STOPPED:
            self._run_cmd(self.distro.get_command('rabbit-mq', 'stop'))
            return 1
        else:
            return 0
