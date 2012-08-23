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
import pkg_resources

from anvil import exceptions as excp
from anvil import colorizer
from anvil import importer
from anvil import log as logging
from anvil import utils

LOG = logging.getLogger(__name__)


class NullVersion(object):

    def __init__(self, name):
        self.name = name

    def __contains__(self, version):
        return True

    def __str__(self):
        return "%s (no version)" % (self.name)


class Registry(object):

    def __init__(self):
        self.installed = dict()
        self.removed = dict()


class Packager(object):

    __meta__ = abc.ABCMeta

    def __init__(self, distro, registry):
        self.distro = distro
        self.registry = registry

    def _parse_version(self, name, version):
        if version:
            # This won't work for all package versions (ie crazy names)
            # but good enough for now...
            if self._contains_version_check(version):
                full_name = "%s%s" %(name, version)
            else:
                full_name = "%s==%s" %(name, version)
            p_version = pkg_resources.Requirement.parse(full_name)
        else:
            p_version = NullVersion(name)
        return p_version

    def _compare_against_installed(self, incoming_version, installed_version):
        if not incoming_version and installed_version:
            # No incoming version, hopefully whats installed is ok
            return True
        if isinstance(installed_version, (NullVersion)):
            # Assume whats installed will work
            # (not really the case all the time)
            return True
        if not incoming_version in installed_version:
            # Not in the range of the installed version (bad!)
            return False
        return True

    def install(self, pkg):
        name = pkg['name']
        version = pkg.get('version')
        if name in self.registry.installed:
            installed_version = self.registry.installed[name]
            if not self._compare_against_installed(version, installed_version):
                raise excp.InstallException(("Version %s previously installed, "
                                             "requested incompatible version %s") % (installed_version, version))
            LOG.debug("Skipping install of %r since it already happened.", name)
        else:
            self._install(pkg)
            LOG.debug("Noting that %s was installed.", name)
            self.registry.installed[name] = self._parse_version(name, version)
            if name in self.registry.removed:
                del(self.registry.removed[name])

    def remove(self, pkg):
        removable = pkg.get('removable')
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

    def _contains_version_check(self, version):
        for c in ['==', '>', "<", '<=', '>=']:
            if version.find(c) != -1:
                return True
        return False


def get_packager_class(package_info, default_packager_class=None):
    packager_name = package_info.get('packager_name') or ''
    packager_name = packager_name.strip()
    if not packager_name:
        return default_packager_class
    packager_class = importer.import_entry_point(packager_name)
    return packager_class
