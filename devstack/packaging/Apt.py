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

import Packager
import Util
from Util import param_replace
import Shell
from Shell import execute

APT_GET = ['apt-get']
APT_REMOVE = ["purge", "-y"]  # should we use remove or purge?
APT_INSTALL = ["install", "-y"]
APT_AUTOREMOVE = ['autoremove', '-y']

#make sure its non-interactive
os.putenv('DEBIAN_FRONTEND', 'noninteractive')


class AptPackager(Packager.Packager):
    def __init__(self):
        Packager.Packager.__init__(self)

    def _form_cmd(self, name, version):
        cmd = name
        if(version and len(version)):
            cmd = cmd + "=" + version
        return cmd

    def _do_cmd(self, base_cmd, pkgs):
        pkgnames = sorted(pkgs.keys())
        cmds = []
        for name in pkgnames:
            version = None
            info = pkgs.get(name)
            if(info):
                version = info.get("version")
            torun = self._form_cmd(name, version)
            cmds.append(torun)
        if(len(cmds)):
            cmd = APT_GET + base_cmd + cmds
            execute(*cmd, run_as_root=True)

    def remove_batch(self, pkgs):
        self._do_cmd(APT_REMOVE, pkgs)
        #clean them out
        cmd = APT_GET + APT_AUTOREMOVE
        execute(*cmd, run_as_root=True)

    def install_batch(self, pkgs, params=None):
        self._do_cmd(APT_INSTALL, pkgs)
