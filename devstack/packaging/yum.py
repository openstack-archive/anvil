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


class YumPackager(pack.Packager):
    def __init__(self, distro):
        pack.Packager.__init__(self, distro)

    def _format_pkg_name(self, name, version):
        cmd = name
        if(version != None and len(version)):
            cmd = cmd + "-" + version
        return cmd

    def _do_cmd(self, base_cmd, pkgs):
        pkgnames = sorted(pkgs.keys())
        cmds = list()
        for name in pkgnames:
            pkg_info = pkgs.get(name)
            torun = self._format_pkg_name(name, pkg_info.get("version"))
            cmds.append(torun)
        if(len(cmds)):
            cmd = YUM_CMD + base_cmd + cmds
            sh.execute(*cmd, run_as_root=True)

    def install_batch(self, pkgs):
        self._do_cmd(YUM_INSTALL, pkgs)
