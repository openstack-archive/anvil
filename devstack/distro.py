# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#    Copyright (C) 2012 Dreamhost Inc. All Rights Reserved.
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

import glob
import os
import platform
import re

import yaml

from devstack import importer
from devstack import log as logging
from devstack import settings
from devstack import utils


LOG = logging.getLogger('devstack.distro')

DISTRO_CONF_DIR = os.path.join(settings.STACK_CONFIG_DIR, 'distros')


class Distro(object):

    @classmethod
    def load_all(cls, path=DISTRO_CONF_DIR):
        """Returns a list of the known distros."""
        results = []
        input_files = glob.glob(os.path.join(DISTRO_CONF_DIR, '*.yaml'))
        if not input_files:
            raise RuntimeError(
                'Did not find any distro definition files in %s' %
                DISTRO_CONF_DIR)
        for filename in input_files:
            try:
                with open(filename, 'r') as f:
                    data = yaml.load(f)
                results.append(cls(**data))
            except Exception as err:
                LOG.warning('Could not load distro definition from %s: %s',
                            filename, err)
        return results

    @classmethod
    def get_current(cls):
        """Returns a Distro instance configured for the current system."""
        plt = platform.platform()
        distname = platform.linux_distribution()[0]
        if not distname:
            raise RuntimeError('Unsupported platform %s' % plt)
        LOG.debug('Looking for distro data for %s (%s)', plt, distname)
        for p in cls.load_all():
            if p.supports_distro(plt):
                LOG.info('Using distro "%s" for platform "%s"', p.name, plt)
                return p
        else:
            raise RuntimeError(
                'No platform configuration data for %s (%s)' %
                (plt, distname))

    def __init__(self, name, distro_pattern, packager_name, commands, components):
        self.name = name
        self.distro_pattern = re.compile(distro_pattern, re.IGNORECASE)
        self.packager_name = packager_name
        self.commands = commands
        self.components = components

    def __repr__(self):
        return "\"%s\" using packager \"%s\"" % (self.name, self.packager_name)

    def get_packages(self, name):
        return self.components[name].get('packages', list())

    def get_pips(self, name):
        return self.components[name].get('pips', list())

    def get_command(self, cmd_key, quiet=False):
        if not quiet:
            return self.commands[cmd_key]
        else:
            return self.commands.get(cmd_key)

    def supports_distro(self, distro_name):
        """Does this distro support the named Linux distro?

        :param distro_name: Return value from platform.linux_distribution().
        """
        return bool(self.distro_pattern.search(distro_name))

    def get_packager_factory(self):
        """Return a factory for a package manager."""
        return importer.import_entry_point(self.packager_name)

    def get_component_action_class(self, name, action):
        """Return the class to use for doing the action w/the component."""
        try:
            entry_point = self.components[name][action]
        except KeyError:
            raise RuntimeError('No class configured to %s %s on %s' %
                               (action, name, self.name))
        return importer.import_entry_point(entry_point)
