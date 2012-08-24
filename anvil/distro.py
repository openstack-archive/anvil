# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#    Copyright (C) 2012 New Dream Network, LLC (DreamHost) All Rights Reserved.
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

import copy
import glob
import platform
import re
import shlex

import yaml

from anvil import colorizer
from anvil import exceptions as excp
from anvil import importer
from anvil import log as logging
from anvil import shell as sh

LOG = logging.getLogger(__name__)


class Distro(object):
 
    def __init__(self, name, platform_pattern, packager_name, commands, components):
        self.name = name
        self._platform_pattern = re.compile(platform_pattern, re.IGNORECASE)
        self._packager_name = packager_name
        self._commands = commands
        self._components = components

    def get_command_config(self, key, *more_keys, **kargs):
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
        end_value = None
        if not quiet:
            end_value = root[end_key]
        else:
            end_value = root.get(end_key)
        return end_value

    def get_command(self, key, *more_keys, **kargs):
        """Retrieves a string for running a command from the setup
        and splits it to return a list.
        """
        val = self.get_command_config(key, *more_keys, **kargs)
        if not val:
            return []
        else:
            return shlex.split(val)

    def known_component(self, name):
        return name in self._components

    def supports_platform(self, platform_name):
        """Does this distro support the named platform?

        :param platform_name: Return value from platform.platform().
        """
        return bool(self._platform_pattern.search(platform_name))

    @property
    def package_manager_class(self):
        """Return a package manager that will work for this distro."""
        return importer.import_entry_point(self._packager_name)

    def extract_component(self, name, action):
        """Return the class + component info to use for doing the action w/the component."""
        try:
            # Use a copy instead of the original
            component_info = copy.deepcopy(self._components[name])
            action_classes = component_info['action_classes']
            entry_point = action_classes[action]
            del action_classes[action]
            cls = importer.import_entry_point(entry_point)
            return ((cls, component_info), action_classes)
        except KeyError:
            raise RuntimeError('No class configured to %r %r on %r' %
                               (action, name, self.name))


def _match_distro(distros):
    plt = platform.platform()
    distro_matched = None
    for d in distros:
        if d.supports_platform(plt):
            distro_matched = d
            break
    if not distro_matched:
        raise excp.ConfigException('No distro matched for platform %r' % plt)
    else:
        LOG.info('Matched distro %s for platform %s',
                 colorizer.quote(distro_matched.name), colorizer.quote(plt))
        return distro_matched


def load(path):
    distro_possibles = []
    input_files = glob.glob(sh.joinpths(path, '*.yaml'))
    if not input_files:
        raise excp.ConfigException(
            'Did not find any distro definition files in %r' %
            path)
    for fn in input_files:
        LOG.debug("Attempting to load distro definition from %r", fn)
        try:
            # Don't use sh here so that we always
            # read this (even if dry-run)
            with open(fn, 'r') as fh:
                contents = fh.read()
                cls_kvs = yaml.safe_load(contents)
                distro_possibles.append(Distro(**cls_kvs))
        except (IOError, yaml.YAMLError) as err:
            LOG.warning('Could not load distro definition from %r: %s', fn, err)
    return _match_distro(distro_possibles)
