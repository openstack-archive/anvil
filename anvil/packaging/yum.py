# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
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

from anvil import log as logging
from anvil import packager as pack
from anvil import shell as sh

from anvil.packaging.helpers import yum_helper

LOG = logging.getLogger(__name__)

YUM_CMD = ['yum']
YUM_INSTALL = ["install", "-y", "-t"]
YUM_REMOVE = ['erase', '-y', "-t"]
NAMED_VERSION_TEMPL = "%s-%s"


class YumPackager(pack.Packager):

    def _format_pkg_name(self, name, version):
        if version:
            return NAMED_VERSION_TEMPL % (name, version)
        else:
            return str(name)

    def _anything_there(self, pkg):
        return yum_helper.get_installed(pkg['name'], pkg.get('version'))

    def _execute_yum(self, cmd, **kargs):
        yum_cmd = YUM_CMD + cmd
        return sh.execute(*yum_cmd, run_as_root=True, check_exit_code=True, **kargs)

    def _remove_special(self, name, info):
        return False

    def _install_special(self, name, info):
        return False

    def _install(self, pkg):
        name = pkg['name']
        if self._install_special(name, pkg):
            return
        else:
            cmd = YUM_INSTALL + [self._format_pkg_name(name, pkg.get("version"))]
            self._execute_yum(cmd)

    def _remove(self, pkg):
        name = pkg['name']
        if not yum_helper.is_installed(name, version=None):
            return
        if self._remove_special(name, pkg):
            return
        cmd = YUM_REMOVE + [self._format_pkg_name(name, pkg.get("version"))]
        self._execute_yum(cmd)
