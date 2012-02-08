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

from devstack import log as logging
from devstack import packager as pack
from devstack import settings
from devstack import shell as sh

LOG = logging.getLogger("devstack.packaging.yum")

#root yum command
YUM_CMD = ['yum']

#tolerant is enabled since we might already have it installed/erased
YUM_INSTALL = ["install", "-y", "-t"]
YUM_REMOVE = ['erase', '-y', "-t"]

#yum separates its pkg names and versions with a dash
VERSION_TEMPL = "%s-%s"

#need to relink for rhel (not a bug!)
RHEL_RELINKS = {
    'python-webob1.0': {
        "src": '/usr/lib/python2.6/site-packages/WebOb-1.0.8-py2.6.egg/webob/',
        'tgt': '/usr/lib/python2.6/site-packages/webob',
    },
    'python-nose1.1': {
        "src": '/usr/lib/python2.6/site-packages/nose-1.1.2-py2.6.egg/nose/',
        'tgt': '/usr/lib/python2.6/site-packages/nose',
    },
}


class YumPackager(pack.Packager):
    def __init__(self, distro, keep_packages):
        pack.Packager.__init__(self, distro, keep_packages)

    def _format_pkg_name(self, name, version):
        if version is not None and len(version):
            return VERSION_TEMPL % (name, version)
        else:
            return name

    def _execute_yum(self, cmd, **kargs):
        return sh.execute(*cmd, run_as_root=True,
            check_exit_code=True,
            **kargs)

    def _remove_special(self, pkgname, pkginfo):
        if self.distro == settings.RHEL6 and pkgname in RHEL_RELINKS:
            #we don't return true here so that
            #the normal package cleanup happens
            sh.unlink(RHEL_RELINKS.get(pkgname).get("tgt"))
        return False

    def _install_rhel_relinks(self, pkgname, pkginfo):
        full_pkg_name = self._format_pkg_name(pkgname, pkginfo.get("version"))
        install_cmd = YUM_CMD + YUM_INSTALL + [full_pkg_name]
        self._execute_yum(install_cmd)
        tgt = RHEL_RELINKS.get(pkgname).get("tgt")
        src = RHEL_RELINKS.get(pkgname).get("src")
        if not sh.islink(tgt):
            # This is actually a feature, EPEL must not conflict with RHEL, so X pkg installs newer version in parallel.
            #
            # This of course doesn't work when running from git like devstack does....
            sh.symlink(src, tgt)
        return True

    def _install_special(self, pkgname, pkginfo):
        if self.distro == settings.RHEL6 and pkgname in RHEL_RELINKS:
            return self._install_rhel_relinks(pkgname, pkginfo)
        return False

    def install_batch(self, pkgs):
        pkg_names = sorted(pkgs.keys())
        pkg_full_names = []
        for name in pkg_names:
            info = pkgs.get(name) or {}
            if self._install_special(name, info):
                continue
            full_pkg_name = self._format_pkg_name(name, info.get("version"))
            pkg_full_names.append(full_pkg_name)
        if pkg_full_names:
            cmd = YUM_CMD + YUM_INSTALL + pkg_full_names
            self._execute_yum(cmd)

    def _remove_batch(self, pkgs):
        pkg_names = sorted(pkgs.keys())
        pkg_full_names = []
        which_removed = []
        for name in pkg_names:
            info = pkgs.get(name) or {}
            removable = info.get('removable', True)
            if not removable:
                continue
            if self._remove_special(name, info):
                which_removed.append(name)
                continue
            full_pkg_name = self._format_pkg_name(name, info.get("version"))
            pkg_full_names.append(full_pkg_name)
            which_removed.append(name)
        if pkg_full_names:
            cmd = YUM_CMD + YUM_REMOVE + pkg_full_names
            self._execute_yum(cmd)
        return which_removed
