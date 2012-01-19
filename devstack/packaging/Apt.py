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
from tempfile import TemporaryFile
import time

import Packager
import Logger

#TODO fix these
from Util import (UBUNTU11, RHEL6)
from Util import param_replace
from Shell import execute

LOG = Logger.getLogger("install.package.apt")

APT_GET = ['apt-get']
APT_PURGE = ["purge", "-y"]
APT_REMOVE = ["remove", "-y"]
APT_INSTALL = ["install", "-y"]
APT_AUTOREMOVE = ['autoremove', '-y']

#should we use remove or purge?
APT_DO_REMOVE = APT_PURGE

#make sure its non-interactive
ENV_ADDITIONS = {'DEBIAN_FRONTEND': 'noninteractive'}

#how versions are expressed by apt
VERSION_TEMPL = "%s=%s"


class AptPackager(Packager.Packager):
    def __init__(self, distro):
        Packager.Packager.__init__(self, distro)

    def _form_cmd(self, name, version):
        if(version and len(version)):
            cmd = VERSION_TEMPL % (name, version)
        else:
            cmd = name
        return cmd

    def _execute_apt(self, cmd, run_as_root, check_exit=True):
        execute(*cmd, run_as_root=run_as_root,
            check_exit_code=check_exit,
            env_overrides=ENV_ADDITIONS)

    def remove_batch(self, pkgs):
        pkgnames = sorted(pkgs.keys())
        #form the needed commands
        cmds = []
        for name in pkgnames:
            info = pkgs.get(name) or {}
            removable = info.get('removable', True)
            if(not removable):
                continue
            if(self._pkg_remove_special(name, info)):
                continue
            full_cmd = self._form_cmd(name, info.get("version"))
            if(full_cmd):
                cmds.append(full_cmd)
        if(len(cmds)):
            cmd = APT_GET + APT_DO_REMOVE + cmds
            self._execute_apt(cmd, True)
        #clean them out
        cmd = APT_GET + APT_AUTOREMOVE
        self._execute_apt(cmd, True)

    def install_batch(self, pkgs):
        pkgnames = sorted(pkgs.keys())
        #form the needed commands
        cmds = []
        for name in pkgnames:
            info = pkgs.get(name) or {}
            if(self._pkg_install_special(name, info)):
                continue
            full_cmd = self._form_cmd(name, info.get("version"))
            if(full_cmd):
                cmds.append(full_cmd)
        #install them
        if(len(cmds)):
            cmd = APT_GET + APT_INSTALL + cmds
            self._execute_apt(cmd, True)

    def _pkg_remove_special(self, name, pkginfo):
        if(name == 'rabbitmq-server' and self.distro == UBUNTU11):
            #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878597
            #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878600
            LOG.info("Handling special remove of %s" % (name))
            full_cmd = self._form_cmd(name, pkginfo.get("version"))
            if(full_cmd):
                cmd = APT_GET + APT_REMOVE + [full_cmd]
                self._execute_apt(cmd, True, True)
                #probably useful to do this
                time.sleep(1)
                #purge
                cmd = APT_GET + APT_PURGE + [full_cmd]
                self._execute_apt(cmd, True)
                return True
        return False

    def _pkg_install_special(self, name, pkginfo):
        if(name == 'rabbitmq-server' and self.distro == UBUNTU11):
            #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878597
            #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878600
            LOG.info("Handling special install of %s" % (name))
            #this seems to be a temporary fix for that bug
            with TemporaryFile() as f:
                full_cmd = self._form_cmd(name, pkginfo.get("version"))
                if(full_cmd):
                    cmd = APT_GET + APT_INSTALL + [full_cmd]
                    execute(*cmd, run_as_root=True, stdout_fh=f, stderr_fh=f, env_overrides=ENV_ADDITIONS)
                    return True
        return False
