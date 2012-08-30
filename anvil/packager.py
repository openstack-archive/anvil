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

from anvil import colorizer
from anvil import importer
from anvil import log as logging
from anvil import type_utils
from anvil import utils

LOG = logging.getLogger(__name__)


class Packager(object):
    __meta__ = abc.ABCMeta

    def __init__(self, distro, remove_default=False):
        self.distro = distro
        self.remove_default = remove_default

    @abc.abstractmethod
    def _anything_there(self, pkg):
        raise NotImplementedError()

    def install(self, pkg):
        installed_already = self._anything_there(pkg)
        if not installed_already:
            self._install(pkg)
            LOG.debug("Installed %s", pkg)
        else:
            LOG.debug("Skipping install of %r since %s is already there.", pkg['name'], installed_already)

    def remove(self, pkg):
        should_remove = self.remove_default
        if 'removable' in pkg:
            should_remove = type_utils.make_bool(pkg['removable'])
        if not should_remove:
            return False
        self._remove(pkg)
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
