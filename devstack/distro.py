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
import platform
import re

import yaml

from devstack import importer
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

LOG = logging.getLogger('devstack.distro')


class Distro(object):

    @classmethod
    def load_all(cls, path=settings.STACK_DISTRO_DIR):
        """Returns a list of the known distros."""
        results = []
        input_files = glob.glob(sh.joinpths(path, '*.yaml'))
        if not input_files:
            raise RuntimeError(
                'Did not find any distro definition files in %s' %
                path)
        for filename in input_files:
            cls_kvs = dict()
            try:
                with open(filename, 'r') as f:
                    cls_kvs = yaml.load(f)
            except (IOError, yaml.YAMLError) as err:
                LOG.warning('Could not load distro definition from %s: %s',
                            filename, err)
            try:
                results.append(utils.construct_instance(cls, **cls_kvs))
            except Exception as err:
                LOG.warning('Could not initialize instance %s using parameter map %s: %s',
                            cls, cls_kvs, err)
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
        self._distro_pattern = re.compile(distro_pattern, re.IGNORECASE)
        self._packager_name = packager_name
        self._commands = commands
        self._components = components

    def __repr__(self):
        return "\"%s\" using packager \"%s\"" % (self.name, self._packager_name)

    def get_command(self, key, *more_keys, **kargs):
        """ Gets a end object for a given set of keys """
        root = self._commands
        acutal_keys = [key] + list(more_keys)
        run_over_keys = acutal_keys[0:-1]
        end_key = acutal_keys[-1]
        quiet = kargs.get('quiet', False)
        for k in run_over_keys:
            if quiet:
                root = root.get(k)
                if root is None:
                    return None
            else:
                root = root[k]
        if not quiet:
            return root[end_key]
        else:
            return root.get(end_key)

    def known_component(self, name):
        return name in self._components

    def supports_distro(self, distro_name):
        """Does this distro support the named Linux distro?

        :param distro_name: Return value from platform.linux_distribution().
        """
        return bool(self._distro_pattern.search(distro_name))

    def get_packager_factory(self):
        """Return a factory for a package manager."""
        return importer.import_entry_point(self._packager_name)

    def extract_component(self, name, action):
        """Return the class + component info to use for doing the action w/the component."""
        try:
            # Use a copy instead of the original
            component_info = dict(self._components[name])
            entry_point = component_info[action]
            cls = importer.import_entry_point(entry_point)
            # Knock all action class info (and any other keys)
            key_deletions = [action] + settings.ACTIONS
            for k in key_deletions:
                if k in component_info:
                    del component_info[k]
            return (cls, component_info)
        except KeyError:
            raise RuntimeError('No class configured to %s %s on %s' %
                               (action, name, self.name))
