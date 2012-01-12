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
import os
import re
import tempfile
from tempfile import TemporaryFile

import Packager
import Util
from Util import param_replace
import Shell
from Shell import execute
import Logger

LOG = Logger.getLogger("install.package.apt")

APT_GET = ['apt-get']
APT_REMOVE = ["purge", "-y"]  # should we use remove or purge?
APT_INSTALL = ["install", "-y"]
APT_AUTOREMOVE = ['autoremove', '-y']

#make sure its non-interactive
os.putenv('DEBIAN_FRONTEND', 'noninteractive')

#not 100% right but it will work for us
#ie we aren't handling : for epochs
#http://www.ducea.com/2006/06/17/ubuntu-package-version-naming-explanation/
UB_PKG_VERSION_REGEX = re.compile(r"^(\d*)\.(\d*)(?:\.(\d*))?-(\d*)ubuntu(\d*)$", re.IGNORECASE)


class AptPackager(Packager.Packager):
    def __init__(self):
        Packager.Packager.__init__(self)

    def _form_cmd(self, name, version):
        cmd = name
        if(version and len(version)):
            cmd = cmd + "=" + version
        return cmd

    def remove_batch(self, pkgs):
        pkgnames = sorted(pkgs.keys())
        #form the needed commands
        cmds = []
        for name in pkgnames:
            info = pkgs.get(name) or {}
            if(_pkg_remove_special(name, info)):
                #handled by the special remove
                continue
            torun = self._form_cmd(name, info.get("version"))
            cmds.append(torun)
        if(len(cmds)):
            cmd = APT_GET + APT_REMOVE + cmds
            execute(*cmd, run_as_root=True)
        #clean them out
        cmd = APT_GET + APT_AUTOREMOVE
        execute(*cmd, run_as_root=True)

    def install_batch(self, pkgs, params=None):
        pkgnames = sorted(pkgs.keys())
        #form the needed commands
        cmds = []
        for name in pkgnames:
            info = pkgs.get(name) or {}
            if(_pkg_install_special(name, info)):
                #handled by the special install
                continue
            torun = self._form_cmd(name, info.get("version"))
            cmds.append(torun)
        #install them
        if(len(cmds)):
            cmd = APT_GET + APT_INSTALL + cmds
            execute(*cmd, run_as_root=True)


def _pkg_remove_special(name, pkginfo):
    #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878597
    #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878600
    if(name == 'rabbitmq-server'):
        version = pkginfo.get('version')
        if(version):
            mtch = UB_PKG_VERSION_REGEX.search(version)
            if(mtch):
                major = (mtch.group(1))
                if(major == None or len(major) == 0):
                    major = 0
                else:
                    major = int(major)
                minor = (mtch.group(2))
                if(minor == None or len(minor) == 0):
                    minor = 0
                else:
                    minor = int(minor)
                if(major <= 2 and minor < 6):
                    LOG.info("Handling special remove of %s v%s" % (name, version))
                    cmd = APT_GET + APT_REMOVE + [name + "=" + version]
                    #wtf, but it seems to work...
                    execute(*cmd, run_as_root=True, check_exit_code=False)
                    execute(*cmd, run_as_root=True)
                    return True
    return False


def _pkg_install_special(name, pkginfo):
    #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878597
    #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878600
    if(name == 'rabbitmq-server'):
        version = pkginfo.get('version')
        if(version):
            mtch = UB_PKG_VERSION_REGEX.search(version)
            if(mtch):
                major = (mtch.group(1))
                if(major == None or len(major) == 0):
                    major = 0
                else:
                    major = int(major)
                minor = (mtch.group(2))
                if(minor == None or len(minor) == 0):
                    minor = 0
                else:
                    minor = int(minor)
                if(major <= 2 and minor < 6):
                    LOG.info("Handling special install of %s v%s" % (name, version))
                    #wtf, but it seems to work...
                    with TemporaryFile() as f:
                        cmd = APT_GET + APT_INSTALL + [name + "=" + version]
                        execute(*cmd, run_as_root=True,
                                stdout_fh=f, stderr_fh=f)
                        return True
    return False
