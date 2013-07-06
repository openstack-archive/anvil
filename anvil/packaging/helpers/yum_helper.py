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

# See http://yum.baseurl.org/api/yum-3.2.26/yum-module.html
from yum import YumBase

from yum.packages import PackageObject

import sys
import tempfile

from anvil import shell as sh


class Requirement(object):
    def __init__(self, name, version):
        self.name = str(name)
        self.version = version

    def __str__(self):
        name = self.name
        if self.version is not None:
            name += "-%s" % (self.version)
        return name

    @property
    def package(self):
        # Form a 'fake' rpm package that
        # can be used to compare against
        # other rpm packages using the
        # standard rpm routines
        my_pkg = PackageObject()
        my_pkg.name = self.name
        if self.version is not None:
            my_pkg.version = str(self.version)
        return my_pkg


class Helper(object):
    # Cache of yumbase object
    _yum_base = None

    @staticmethod
    def _get_yum_base():
        if Helper._yum_base is None:
            _yum_base = YumBase()
            _yum_base.setCacheDir(force=True)
            Helper._yum_base = _yum_base
        return Helper._yum_base

    def is_installed(self, name):
        if len(self.get_installed(name)):
            return True
        else:
            return False

    def run_transaction(self, actions, cmd_options=None):
        with tempfile.NamedTemporaryFile(suffix=".txn") as fh:
            for a in actions:
                fh.write("%s\n" % (a.strip()))
            if 'run' not in actions:
                fh.write("run\n")
            if 'exit' not in actions:
                fh.write("exit\n")
            fh.flush()
            cmdline = ['yum', '-y']
            if cmd_options:
                cmdline.extend(cmd_options)
            cmdline.extend(['shell', fh.name])
            sh.execute(cmdline, stdout_fh=sys.stdout, stderr_fh=sys.stderr)

    def get_available(self):
        base = Helper._get_yum_base()
        pkgs = base.doPackageLists(showdups=True)
        avail = list(pkgs.available)
        avail.extend(pkgs.installed)
        return avail

    def get_installed(self, name):
        base = Helper._get_yum_base()
        pkgs = base.doPackageLists(pkgnarrow='installed',
                                   ignore_case=True, patterns=[name])
        if pkgs.installed:
            whats_installed = list(pkgs.installed)
        else:
            whats_installed = []
        return whats_installed
