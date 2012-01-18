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

import Logger
from Component import (ComponentBase, RuntimeComponent,
                       PkgUninstallComponent, PkgInstallComponent)
from Exceptions import (StartException, StopException,
                    StatusException, RestartException)
import Packager
from Util import (RABBIT, UBUNTU11)
from Trace import (TraceReader,
                    IN_TRACE)
from Shell import (execute)

LOG = Logger.getLogger("install.rabbit")
TYPE = RABBIT

#hopefully these are distro independent..
START_CMD = ['service', "rabbitmq-server", "start"]
STOP_CMD = ['service', "rabbitmq-server", "stop"]
STATUS_CMD = ['service', "rabbitmq-server", "status"]
RESTART_CMD = ['service', "rabbitmq-server", "restart"]
PWD_CMD = ['rabbitmqctl', 'change_password', 'guest']


class RabbitUninstaller(PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        PkgUninstallComponent.__init__(self, TYPE, *args, **kargs)


class RabbitInstaller(PkgInstallComponent):
    def __init__(self, *args, **kargs):
        PkgInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.runtime = RabbitRuntime(*args, **kargs)

    def _get_download_location(self):
        return (None, None)

    def _setup_pw(self):
        passwd = self.cfg.getpw("passwords", "rabbit")
        cmd = PWD_CMD + [passwd]
        execute(*cmd, run_as_root=True)

    def install(self):
        pres = PkgInstallComponent.install(self)
        #ensure setup right
        self._setup_pw()
        #restart it to make sure its ok to go
        self.runtime.restart()
        return pres


class RabbitRuntime(ComponentBase, RuntimeComponent):
    def __init__(self, *args, **kargs):
        ComponentBase.__init__(self, TYPE, *args, **kargs)
        self.tracereader = TraceReader(self.tracedir, IN_TRACE)

    def start(self):
        pkgsinstalled = self.tracereader.packages_installed()
        if(len(pkgsinstalled) == 0):
            msg = "Can not start %s since it was not installed" % (TYPE)
            raise StartException(msg)
        if(self.status().find('start') == -1):
            self._run_cmd(START_CMD)
        return None

    def status(self):
        pkgsinstalled = self.tracereader.packages_installed()
        if(len(pkgsinstalled) == 0):
            msg = "Can not check the status of %s since it was not installed" % (TYPE)
            raise StatusException(msg)
        (sysout, stderr) = execute(*STATUS_CMD, run_as_root=True)
        return sysout.strip().lower()

    def _run_cmd(self, cmd):
        if(self.distro == UBUNTU11):
            with TemporaryFile() as f:
                execute(*cmd, run_as_root=True,
                            stdout_fh=f, stderr_fh=f)
        else:
            execute(*cmd, run_as_root=True)

    def restart(self):
        pkgsinstalled = self.tracereader.packages_installed()
        if(len(pkgsinstalled) == 0):
            msg = "Can not check the status of %s since it was not installed" % (TYPE)
            raise RestartException(msg)
        self._run_cmd(RESTART_CMD)
        return None

    def stop(self):
        pkgsinstalled = self.tracereader.packages_installed()
        if(len(pkgsinstalled) == 0):
            msg = "Can not stop %s since it was not installed" % (TYPE)
            raise StopException(msg)
        if(self.status().find('stop') == -1):
            self._run_cmd(STOP_CMD)
        return None
