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
from Util import param_replace
from Shell import execute
import Logger

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
            removable = info.get('removable', True)
            if(not removable):
                continue
            if(_pkg_remove_special(name, info)):
                #handled by the special remove
                continue
            torun = self._form_cmd(name, info.get("version"))
            cmds.append(torun)
        if(len(cmds)):
            cmd = APT_GET + APT_DO_REMOVE + cmds
            execute(*cmd, run_as_root=True,
                env_overrides=ENV_ADDITIONS)
        #clean them out
        cmd = APT_GET + APT_AUTOREMOVE
        execute(*cmd, run_as_root=True,
            env_overrides=ENV_ADDITIONS)

    def install_batch(self, pkgs):
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
            execute(*cmd, run_as_root=True,
                env_overrides=ENV_ADDITIONS)


def _extract_version(version):
    version_info = dict()
    if(version.lower().find("ubuntu") != -1):
        mtch = UB_PKG_VERSION_REGEX.search(version)
        if(mtch):
            major = mtch.group(1)
            major = int(major) if major != None else -1
            minor = mtch.group(2)
            minor = int(minor) if minor != None else -1
            release = mtch.group(3)
            release = int(release) if release != None else -1
            debian_version = mtch.group(4)
            debian_version = int(debian_version) if debian_version != None else -1
            ubuntu_version = mtch.group(5)
            ubuntu_version = int(ubuntu_version) if ubuntu_version != None else -1
            version_info['type'] = 'ubuntu'
            version_info['major'] = major
            version_info['minor'] = minor
            version_info['release'] = release
            version_info['debian_version'] = debian_version
            version_info['ubuntu_version'] = ubuntu_version
    return version_info


def _pkg_remove_special(name, pkginfo):
    #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878597
    #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878600
    if(name == 'rabbitmq-server'):
        version = pkginfo.get('version')
        version_info = _extract_version(version)
        if(len(version_info)):
            if(version_info.get('type') == 'ubuntu' and
                version_info.get('major') <= 2 and
                version_info.get('minor') < 6):
                LOG.info("Handling special remove of %s v%s" % (name, version))
                #the first time seems to fail with exit code 100 but the second
                #time seems to not fail, pretty weird, most likely the above bugs
                cmd = APT_GET + APT_REMOVE + [name + "=" + version]
                execute(*cmd, run_as_root=True,
                    check_exit_code=False, env_overrides=ENV_ADDITIONS)
                #probably useful to do this
                time.sleep(1)
                cmd = APT_GET + APT_PURGE + [name + "=" + version]
                execute(*cmd, run_as_root=True,
                    env_overrides=ENV_ADDITIONS)
                return True
    return False


def _pkg_install_special(name, pkginfo):
    #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878597
    #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878600
    if(name == 'rabbitmq-server'):
        version = pkginfo.get('version')
        version_info = _extract_version(version)
        if(len(version_info)):
            if(version_info.get('type') == 'ubuntu' and
                version_info.get('major') <= 2 and
                version_info.get('minor') < 6):
                LOG.info("Handling special install of %s v%s" % (name, version))
                #this seems to be a temporary fix for that bug
                with TemporaryFile() as f:
                    cmd = APT_GET + APT_INSTALL + [name + "=" + version]
                    execute(*cmd, run_as_root=True,
                            stdout_fh=f, stderr_fh=f,
                            env_overrides=ENV_ADDITIONS)
                    return True
    return False
