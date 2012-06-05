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

from anvil import component as comp
from anvil import constants
from anvil import log as logging
from anvil import shell as sh

LOG = logging.getLogger(__name__)


class QpidUninstaller(comp.PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgUninstallComponent.__init__(self, *args, **kargs)


class QpidInstaller(comp.PkgInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgInstallComponent.__init__(self, *args, **kargs)


class QpidRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, *args, **kargs)
        self.wait_time = max(self.cfg.getint('DEFAULT', 'service_wait_seconds'), 1)

    def start(self):
        if self._status() != constants.STATUS_STARTED:
            start_cmd = self.distro.get_command('qpid', 'start')
            sh.execute(*start_cmd, run_as_root=True, check_exit_code=True)
            LOG.info("Please wait %s seconds while it starts up." % self.wait_time)
            sh.sleep(self.wait_time)
            return 1
        else:
            return 0

    def stop(self):
        if self._status() != constants.STATUS_STOPPED:
            stop_cmd = self.distro.get_command('qpid', 'stop')
            sh.execute(*stop_cmd, run_as_root=True, check_exit_code=True)
            return 1
        else:
            return 0

    def restart(self):
        LOG.info("Restarting your qpid daemon.")
        restart_cmd = self.distro.get_command('qpid', 'restart')
        sh.execute(*restart_cmd, run_as_root=True, check_exit_code=True)
        LOG.info("Please wait %s seconds while it restarts." % self.wait_time)
        sh.sleep(self.wait_time)
        return 1

    def _status(self):
        status_cmd = self.distro.get_command('qpid', 'status')
        (sysout, stderr) = sh.execute(*status_cmd, run_as_root=True, check_exit_code=False)
        combined = (str(sysout) + str(stderr)).lower()
        if combined.find("running") != -1:
            return constants.STATUS_STARTED
        elif combined.find("stop") != -1 or \
             combined.find('unrecognized') != -1:
            return constants.STATUS_STOPPED
        else:
            return constants.STATUS_UNKNOWN
