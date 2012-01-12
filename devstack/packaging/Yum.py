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

import Packager
import Logger

LOG = Logger.getLogger("install.package.Yum")

class YumPackager(Packager.Packager):
    def __init__(self):
        Packager.Packager.__init__(self)

    def install_batch(self, pkgs):
        pkgnames = pkgs.keys()
        pkgnames.sort()
        cmds = []
        LOG.debug("Attempt to install pkgs:%s" % pkgnames)
        for name in pkgnames:
            version = None
            torun = name
            info = pkgs.get(name)
            if(info != None):
                version = info.get("version")
            if(version != None):
                torun = torun + "-" + version
            cmds.append(torun)
        if(len(cmds)):
            LOG.debug("Final command:%s" % cmds)
            #execute(*cmd, run_as_root=True)
