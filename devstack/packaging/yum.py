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

from devstack import exceptions as excp
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
RHEL_WEBOB_LINK = {
    "src": '/usr/lib/python2.6/site-packages/WebOb-1.0.8-py2.6.egg/webob/',
    'tgt': '/usr/lib/python2.6/site-packages/webob',
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
        if pkgname == 'python-webob1.0' and self.distro == settings.RHEL6:
            self._remove_webob_rhel()
            #we don't return true here so that
            #the normal package cleanup happens
        return False

    def _remove_webob_rhel(self):
        tgt = RHEL_WEBOB_LINK.get("tgt")
        if sh.islink(tgt):
            rm_cmd = ['rm', tgt]
            sh.execute(*rm_cmd, run_as_root=True)

    def _install_webob_rhel(self, pkgname, pkginfo):
        full_pkg_name = self._format_pkg_name(pkgname, pkginfo.get("version"))
        install_cmd = YUM_CMD + YUM_INSTALL + [full_pkg_name]
        self._execute_yum(install_cmd)
        tgt = RHEL_WEBOB_LINK.get("tgt")
        src = RHEL_WEBOB_LINK.get("src")
        if not sh.islink(tgt):
            #This is actually a feature, EPEL must not conflict with RHEL, so python-webob1.0 installs newer version in parallel.
            #
            #This of course doesn't work when running from git like devstack does....
            #
            #$ cat /usr/share/doc/python-webob1.0-1.0.8/README.Fedora
            #
            # To use version 1.0.8 of python WebOB it is nescesary
            # to explicitly load it so as not to get the system version
            # of WebOb.
            #
            # Manually modifying sys.path is an easy and reliable way
            # to use this module.
            #
            # >>> import sys
            # >>> sys.path.insert(0, '/usr/lib/python2.6/site-packages/WebOb-1.0.8-py2.6.egg')
            # >>> import webob
            link_cmd = ['ln', '-s', src, tgt]
            sh.execute(*link_cmd, run_as_root=True)
        return True

    def _install_special(self, pkgname, pkginfo):
        if pkgname == 'python-webob1.0' and self.distro == settings.RHEL6:
            return self._install_webob_rhel(pkgname, pkginfo)
        return False

    def install_batch(self, pkgs):
        pkg_names = sorted(pkgs.keys())
        pkg_full_names = list()
        for name in pkg_names:
            info = pkgs.get(name) or {}
            if self._install_special(name, info):
                continue
            full_pkg_name = self._format_pkg_name(name, info.get("version"))
            if full_pkg_name:
                pkg_full_names.append(full_pkg_name)
        if pkg_full_names:
            cmd = YUM_CMD + YUM_INSTALL + pkg_full_names
            self._execute_yum(cmd)

    def remove_batch(self, pkgs):
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
            if full_pkg_name:
                pkg_full_names.append(full_pkg_name)
                which_removed.append(name)
        if pkg_full_names:
            cmd = YUM_CMD + YUM_REMOVE + pkg_full_names
            self._execute_yum(cmd)
        return which_removed
