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

from anvil import shell as sh

# See http://yum.baseurl.org/api/yum-3.2.26/yum-module.html
from yum import YumBase
from yum.packages import PackageObject

# Cache of yumbase object
_yum_base = None


def _make_yum_base():
    global _yum_base
    if _yum_base is None:
        # This seems needed...
        # otherwise 'cannot open Packages database in /var/lib/rpm' starts to happen
        with sh.Rooted(True):
            _yum_base = YumBase()
            _yum_base.setCacheDir(force=True)
    return _yum_base


def is_installed(name, version=None):
    if get_installed(name, version):
        return True
    else:
        return False


def get_installed(name, version=None):
    # This seems needed...
    # otherwise 'cannot open Packages database in /var/lib/rpm' starts to happen
    with sh.Rooted(True):
        yb = _make_yum_base()
        pkg_obj = yb.doPackageLists(pkgnarrow='installed',
                                    ignore_case=True, patterns=[name])
    whats_installed = pkg_obj.installed
    if not whats_installed:
        return None
    # Compare whats installed to a fake package that will
    # represent what might be installed...
    fake_pkg = PackageObject()
    fake_pkg.name = name
    if version:
        fake_pkg.version = str(version)
    for installed_pkg in whats_installed:
        if installed_pkg.verGE(fake_pkg):
            return installed_pkg
    return None
