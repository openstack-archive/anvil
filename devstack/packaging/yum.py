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

from devstack import log as logging
from devstack import packager as pack
from devstack import shell as sh

LOG = logging.getLogger("devstack.packaging.yum")
YUM_CMD = ['yum']
YUM_INSTALL = ["install", "-y"]
YUM_REMOVE = ['erase', '-y']


class YumPackager(pack.Packager):
    def __init__(self, distro):
        pack.Packager.__init__(self, distro)

    def _format_pkg_name(self, name, version):
        cmd = name
        if(version != None and len(version)):
            cmd = cmd + "-" + version
        return cmd

    def _execute_yum(self, cmd, **kargs):
        return sh.execute(*cmd, run_as_root=True,
            check_exit_code=True,
            **kargs)

    def _remove_special(self, pkgname, pkginfo):
        return False

    def _install_special(self, pkgname, pkginfo):
        return False

    def install_batch(self, pkgs):
        pkg_names = sorted(pkgs.keys())
        pkg_full_names = list()
        for name in pkg_names:
            info = pkgs.get(name) or {}
            if(self._install_special(name, info)):
                continue
            full_pkg_name = self._format_pkg_name(name, info.get("version"))
            if(full_pkg_name):
                pkg_full_names.append(full_pkg_name)
        if(len(pkg_full_names)):
            cmd = YUM_CMD + YUM_INSTALL + pkg_full_names
            self._execute_yum(cmd)

    def remove_batch(self, pkgs):
        pkg_names = sorted(pkgs.keys())
        pkg_full_names = []
        which_removed = []
        for name in pkg_names:
            info = pkgs.get(name) or {}
            removable = info.get('removable', True)
            if(not removable):
                continue
            if(self._remove_special(name, info)):
                which_removed.append(name)
                continue
            full_pkg_name = self._format_pkg_name(name, info.get("version"))
            if(full_pkg_name):
                pkg_full_names.append(full_pkg_name)
                which_removed.append(name)
        if(len(pkg_full_names)):
            cmd = YUM_CMD + YUM_REMOVE + pkg_full_names
            self._execute_yum(cmd)
        return which_removed
