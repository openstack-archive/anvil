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

import abc

from anvil import exceptions as excp
from anvil import colorizer
from anvil import importer
from anvil import log as logging
from anvil import utils

LOG = logging.getLogger(__name__)

# Install comparison constants
DO_INSTALL = 1
ADEQUATE_INSTALLED = 2

# Removal status constants
REMOVED_OK = 1
NOT_EXISTENT = 2


class Packager(object):
    __meta__ = abc.ABCMeta

    def __init__(self, distro):
        self.distro = distro

    def _compare_against_installed(self, pkg):
        return DO_INSTALL

    def install(self, pkg):
        install_check = self._compare_against_installed(pkg)
        if install_check == DO_INSTALL:
            self._install(pkg)
            LOG.debug("Installed %s", pkg)
        elif install_check == ADEQUATE_INSTALLED:
            LOG.debug("Skipping install of %r since a newer/same version is already happened.", pkg['name'])

    def remove(self, pkg):
        removable = pkg.get('removable')
        if not removable:
            return False
        rst = self._remove(pkg)
        if rst == NOT_EXISTENT:
            LOG.debug("Removal of %r did not occur since it already happened or did not exist to remove.", pkg['name'])
        return True

    def pre_install(self, pkg, params=None):
        cmds = pkg.get('pre-install')
        if cmds:
            LOG.info("Running pre-install commands for package %s.", colorizer.quote(pkg['name']))
            utils.execute_template(*cmds, params=params)

    def post_install(self, pkg, params=None):
        cmds = pkg.get('post-install')
        if cmds:
            LOG.info("Running post-install commands for package %s.", colorizer.quote(pkg['name']))
            utils.execute_template(*cmds, params=params)

    @abc.abstractmethod
    def _remove(self, pkg):
        raise NotImplementedError()

    @abc.abstractmethod
    def _install(self, pkg):
        raise NotImplementedError()





def get_packager_class(package_info, default_packager_class=None):
    packager_name = package_info.get('packager_name') or ''
    packager_name = packager_name.strip()
    if not packager_name:
        return default_packager_class
    return importer.import_entry_point(packager_name)
