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
from devstack import exceptions as excp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import trace as tr

LOG = logging.getLogger("devstack.components.rabbit")

#id
TYPE = settings.RABBIT

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
        passwd = self.cfg.get("passwords", "rabbit")
        cmd = PWD_CMD + [passwd]
        sh.execute(*cmd, run_as_root=True)

    def post_install(self):
        parent_result = comp.PkgInstallComponent.post_install(self)
        self._setup_pw()
        self.runtime.restart()
        return parent_result


class RabbitRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, TYPE, *args, **kargs)
        self.tracereader = tr.TraceReader(self.tracedir, tr.IN_TRACE)

    def start(self):
        if self.status() == comp.STATUS_STOPPED:
            self._run_cmd(START_CMD)
            return 1
        else:
            return 0

    def status(self):
        pkgsinstalled = self.tracereader.packages_installed()
        if not pkgsinstalled:
            msg = "Can not check the status of %s since it was not installed" % (TYPE)
            raise excp.StatusException(msg)
        #this has got to be the worst status output
        #i have ever seen (its like a weird mix json)
        (sysout, _) = sh.execute(*STATUS_CMD,
                        run_as_root=True,
                        check_exit_code=False)
        if sysout.find('nodedown') != -1 or sysout.find("unable to connect to node") != -1:
            return comp.STATUS_STOPPED
        elif sysout.find('running_applications') != -1:
            return comp.STATUS_STARTED
        else:
            return comp.STATUS_UNKNOWN

    def _run_cmd(self, cmd):
        if self.distro == settings.UBUNTU11:
            #this seems to fix one of the bugs with rabbit mq starting and stopping
            #not cool, possibly connected to the following bugs:
            #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878597
            #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878600
            with TemporaryFile() as f:
                sh.execute(*cmd, run_as_root=True,
                            stdout_fh=f, stderr_fh=f)
        else:
            sh.execute(*cmd, run_as_root=True)

    def restart(self):
        self._run_cmd(RESTART_CMD)
        return 1

    def stop(self):
        if self.status() == comp.STATUS_STARTED:
            self._run_cmd(STOP_CMD)
            return 1
        else:
            return 0
