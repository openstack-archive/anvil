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

from devstack import importer
from devstack import log as logging
from devstack import utils

LOG = logging.getLogger("devstack.packager")


class PackageRegistry(object):

    def __init__(self):
        self.installed = dict()
        self.removed = dict()


class Packager(object):

    __meta__ = abc.ABCMeta

    def __init__(self, distro):
        self.distro = distro
        self.registry = PackageRegistry()

    def install(self, pkg):
        name = pkg['name']
        version = pkg.get('version')
        skip_install = False
        if name in self.registry.installed:
            existing_version = self.registry.installed[name]
            if version == existing_version:
                LOG.debug("Skipping install of %r since it already happened.", name)
                skip_install = True
            else:
                if existing_version is not None:
                    if utils.versionize(existing_version) < utils.versionize(version):
                        LOG.warn("A request has come in for a newer version of %r v(%s), when v(%s) was previously installed!", name, version, existing_version)
                    elif utils.versionize(existing_version) > utils.versionize(version):
                        LOG.warn("A request has come in for a older version of %r v(%s), when v(%s) was previously installed!", name, version, existing_version)
                else:
                    LOG.warn("A request has come in for a different version of %r v(%s), when a unspecified version was previously installed!", name, version)
        if not skip_install:
            self._install(pkg)
            LOG.debug("Noting that %r - v(%s) was installed.", name, (version or "??"))
            self.registry.installed[name] = version
            if name in self.registry.removed:
                del(self.registry.removed[name])

    def remove(self, pkg):
        removable = pkg.get('removable', True)
        if not removable:
            return False
        name = pkg['name']
        if name in self.registry.removed:
            LOG.debug("Skipping removal of %r since it already happened.", name)
        else:
            self._remove(pkg)
            LOG.debug("Noting that %r was removed.", name)
            self.registry.removed[name] = True
            if name in self.registry.installed:
                del(self.registry.installed[name])
        return True

    def pre_install(self, pkg, params=None):
        cmds = pkg.get('pre-install')
        if cmds:
            LOG.info("Running pre-install commands for package %r.", pkg['name'])
            utils.execute_template(*cmds, params=params)

    def post_install(self, pkg, params=None):
        cmds = pkg.get('post-install')
        if cmds:
            LOG.info("Running post-install commands for package %r.", pkg['name'])
            utils.execute_template(*cmds, params=params)

    @abc.abstractmethod
    def _remove(self, pkg):
        pass

    @abc.abstractmethod
    def _install(self, pkg):
        pass


class PackagerFactory(object):

    PACKAGER_KEY_NAME = 'packager_name'

    def __init__(self, distro, default_packager):
        self.default_packager = default_packager
        self.distro = distro
        self.fetched_packagers = dict()

    def get_packager_for(self, pkg_info):
        if self.PACKAGER_KEY_NAME in pkg_info:
            packager_name = pkg_info[self.PACKAGER_KEY_NAME]
            if packager_name in self.fetched_packagers:
                packager = self.fetched_packagers[packager_name]
            else:
                LOG.debug('Loading custom package manager %r for package %r', packager_name, pkg_info['name'])
                packager = importer.import_entry_point(packager_name)(self.distro)
                self.fetched_packagers[packager_name] = packager
        else:
            packager = self.default_packager
        return packager
