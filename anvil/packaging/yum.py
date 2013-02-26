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


class MultiplePackageSolutions(Exception):
    pass


class YumPackager(pack.Packager):
    def __init__(self, distro, remove_default=False):
        pack.Packager.__init__(self, distro, remove_default)
        self.helper = yum_helper.Helper()

    def _anything_there(self, pkg):
        req = extract_requirement(pkg)
        whats_installed = self.helper.get_installed(req.name)
        if len(whats_installed) == 0:
            return None
        # Check if whats installed will work, and if it won't
        # then hopefully whats being installed will and
        # something later doesn't come by and change it...
        for p in whats_installed:
            if p.verGE(req.package):
                return p
        # Warn that incompat. versions could be installed...
        LOG.warn("There was %s matches to %s found, none satisified our request!",
                 len(whats_installed), req)
        return None

    def match_pip_2_package(self, pip_requirement):
        possible_pkgs = self._match_pip_name(pip_requirement)
        if not possible_pkgs:
            return None

        def match_version(yum_pkg):
            version = str(yum_pkg.version)
            if version in pip_requirement:
                return True
            return False

        satisfying_packages = [p for p in possible_pkgs if match_version(p)]
        if not satisfying_packages:
            return None

        if len(satisfying_packages) > 1:
            msg = "Multiple satisfying packages found for requirement %s: %s" % (pip_requirement,
                                                                                 ", ".join([str(p) for p in satisfying_packages]))
            raise MultiplePackageSolutions(msg)
        else:
            return satisfying_packages[0]

    def _match_pip_name(self, pip_requirement):
        # See if we can find anything that might work
        # by looking at our available yum packages.
        all_available = self.helper.get_available()

        # Try a few name variations to see if we can find a matching
        # rpm for a given pip, using a little apriori knowledge about
        # how redhat usually does it...

        def is_exact_match(yum_pkg):
            possible_names = [
                "python-%s" % (pip_requirement.project_name),
                "python-%s" % (pip_requirement.key),
            ]
            pkg_name = str(yum_pkg.name)
            if skip_packages_named(pkg_name):
                return False
            if pkg_name in possible_names:
                return True
            return False

        def is_weak_exact_match_name(yum_pkg):
            possible_names = [
                pip_requirement.project_name,
                pip_requirement.key,
                "python-%s" % (pip_requirement.project_name),
                "python-%s" % (pip_requirement.key),
            ]
            pkg_name = str(yum_pkg.name)
            if skip_packages_named(pkg_name):
                return False
            if pkg_name in possible_names:
                return True
            return False

        def skip_packages_named(name):
            # Skip on ones that end with '-doc' or 'src'
            name = name.lower()
            if name.endswith('-doc'):
                return True
            if name.endswith('-src'):
                return True
            return False

        def is_partial_match_name(yum_pkg):
            pkg_name = str(yum_pkg.name)
            if skip_packages_named(pkg_name):
                return False
            for n in possible_names:
                if pkg_name.find(n) != -1:
                    return True
            return False

        for func in [is_exact_match, is_weak_exact_match_name, is_partial_match_name]:
            matches = [p for p in all_available if func(p)]
            if len(matches):
                return matches
        return []

    def _execute_yum(self, cmd, **kargs):
        yum_cmd = YUM_CMD + cmd
        return sh.execute(*yum_cmd, run_as_root=True,
                          check_exit_code=True, **kargs)

    def direct_install(self, filename):
        cmd = YUM_INSTALL + [filename]
        self._execute_yum(cmd)

    def _remove_special(self, name, info):
        return False

    def _install_special(self, name, info):
        return False

    def _install(self, pkg):
        req = extract_requirement(pkg)
        if self._install_special(req.name, pkg):
            return
        else:
            cmd = YUM_INSTALL + [str(req)]
            self._execute_yum(cmd)

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
