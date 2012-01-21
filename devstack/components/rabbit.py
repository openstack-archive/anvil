# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

from devstack import component as comp
from devstack import constants
from devstack import exceptions as excp
from devstack import log as logging
from devstack import shell as sh
from devstack import trace as tr
from devstack import utils

LOG = logging.getLogger("devstack.components.rabbit")
TYPE = constants.RABBIT

#hopefully these are distro independent..
START_CMD = ['service', "rabbitmq-server", "start"]
STOP_CMD = ['service', "rabbitmq-server", "stop"]
STATUS_CMD = ['service', "rabbitmq-server", "status"]
RESTART_CMD = ['service', "rabbitmq-server", "restart"]
PWD_CMD = ['rabbitmqctl', 'change_password', 'guest']


class RabbitUninstaller(comp.PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgUninstallComponent.__init__(self, TYPE, *args, **kargs)


class RabbitInstaller(comp.PkgInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.runtime = RabbitRuntime(*args, **kargs)

    def _setup_pw(self):
        passwd = self.cfg.getpw("passwords", "rabbit")
        cmd = PWD_CMD + [passwd]
        sh.execute(*cmd, run_as_root=True)

    def post_install(self):
        parent_result = comp.PkgInstallComponent.post_install(self)
        self._setup_pw()
        self.runtime.restart()
        return parent_result


class RabbitRuntime(comp.NullRuntime):
    def __init__(self, *args, **kargs):
        comp.NullRuntime.__init__(self, TYPE, *args, **kargs)
        self.tracereader = tr.TraceReader(self.tracedir, tr.IN_TRACE)

    def start(self):
        pkgsinstalled = self.tracereader.packages_installed()
        if(len(pkgsinstalled) == 0):
            msg = "Can not start %s since it was not installed" % (TYPE)
            raise excp.StartException(msg)
        if(self.status().find('start') == -1):
            self._run_cmd(START_CMD)
        return None

    def status(self):
        pkgsinstalled = self.tracereader.packages_installed()
        if(len(pkgsinstalled) == 0):
            msg = "Can not check the status of %s since it was not installed" % (TYPE)
            raise excp.StatusException(msg)
        (sysout, stderr) = sh.execute(*STATUS_CMD, run_as_root=True)
        return sysout.strip().lower()

    def _run_cmd(self, cmd):
        if(self.distro == constants.UBUNTU11):
            with TemporaryFile() as f:
                sh.execute(*cmd, run_as_root=True,
                            stdout_fh=f, stderr_fh=f)
        else:
            sh.execute(*cmd, run_as_root=True)

    def restart(self):
        pkgsinstalled = self.tracereader.packages_installed()
        if(len(pkgsinstalled) == 0):
            msg = "Can not check the status of %s since it was not installed" % (TYPE)
            raise excp.RestartException(msg)
        self._run_cmd(RESTART_CMD)
        return None

    def stop(self):
        pkgsinstalled = self.tracereader.packages_installed()
        if(len(pkgsinstalled) == 0):
            msg = "Can not stop %s since it was not installed" % (TYPE)
            raise excp.StopException(msg)
        if(self.status().find('stop') == -1):
            self._run_cmd(STOP_CMD)
        return None
