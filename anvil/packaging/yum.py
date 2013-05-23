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

from anvil import exceptions as excp
from anvil import log as logging
from anvil import packager as pack
from anvil import shell as sh

from anvil.packaging.helpers import yum_helper

LOG = logging.getLogger(__name__)

YUM_CMD = ['yum']
YUM_INSTALL = ["install", "-y", "-t"]
YUM_REMOVE = ['erase', '-y', "-t"]


# TODO(aababilov): use it in `Requires:' at prepare.py
def extract_requirement(pkg_info):
    p_name = pkg_info.get('name', '')
    p_name = p_name.strip()
    if not p_name:
        raise ValueError("Yum requirement provided with an empty name")
    p_version = pkg_info.get('version')
    if p_version is not None:
        if isinstance(p_version, (int, float, long)):
            p_version = str(p_version)
        if not isinstance(p_version, (str, basestring)):
            raise TypeError("Yum requirement version must be a string or numeric type")
    return yum_helper.Requirement(p_name, p_version)


class MultiplePackageSolutions(excp.DependencyException):
    pass


class YumPackager(pack.Packager):
    def __init__(self, distro, remove_default=False):
        pack.Packager.__init__(self, distro, remove_default)
        self.helper = yum_helper.Helper()

    def _execute_yum(self, cmd, **kargs):
        yum_cmd = YUM_CMD + cmd
        return sh.execute(*yum_cmd, run_as_root=True,
                          check_exit_code=True, **kargs)

    def direct_install(self, filename):
        cmd = YUM_INSTALL + [filename]
        self._execute_yum(cmd)

    def _remove_special(self, name, info):
        return False

    def _remove(self, pkg):
        req = extract_requirement(pkg)
        whats_there = self.helper.get_installed(req.name)
        matched = False
        if req.version is None and len(whats_there):
            # Always matches...
            matched = True
        else:
            for p in whats_there:
                if p.verEQ(req.package):
                    matched = True
        if not len(whats_there):
            # Nothing installed
            return
        if not matched:
            # Warn that incompat. version could be uninstalled
            LOG.warn("Removing package named %s even though %s packages with different versions exist",
                     req, len(whats_there))
        if self._remove_special(req.name, pkg):
            return
        # Not removing specific version, this could
        # cause problems but should be good enough until
        # it does cause problems...
        cmd = YUM_REMOVE + [req.name]
        self._execute_yum(cmd)

    def pre_install(self, pkg, params=None):
        """pre-install is handled in openstack-deps %pre script.
        """
        pass

    def post_install(self, pkg, params=None):
        """post-install is handled in openstack-deps %post script.
        """
        pass
