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

import collections
import copy
import glob
import os
import platform
import re
import shlex

import six

from anvil import exceptions as excp
from anvil import importer
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

LOG = logging.getLogger(__name__)

Component = collections.namedtuple(  # pylint: disable=C0103
    "Component", 'entry_point,options,siblings')


class Distro(object):
    def __init__(self,
                 name, platform_pattern,
                 install_helper, dependency_handler,
                 commands, components):
        self.name = name
        self._platform_pattern = re.compile(platform_pattern, re.IGNORECASE)
        self._install_helper = install_helper
        self._dependency_handler = dependency_handler
        self._commands = commands
        self._components = components

    def _fetch_value(self, root, keys, quiet):
        end_key = keys[-1]
        for k in keys[0:-1]:
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

    def get_dependency_config(self, key, *more_keys, **kwargs):
        root = dict(self._dependency_handler)
        # NOTE(harlowja): Don't allow access to the dependency handler class
        # name. Access should be via the property instead.
        root.pop('name', None)
        keys = [key] + list(more_keys)
        return self._fetch_value(root, keys, kwargs.get('quiet', False))

    def get_command_config(self, key, *more_keys, **kwargs):
        root = dict(self._commands)
        keys = [key] + list(more_keys)
        return self._fetch_value(root, keys, kwargs.get('quiet', False))

    def get_command(self, key, *more_keys, **kwargs):
        """Retrieves a string for running a command from the setup
        and splits it to return a list.
        """
        val = self.get_command_config(key, *more_keys, **kwargs)
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
    def install_helper_class(self):
        """Return an install helper that will work for this distro."""
        return importer.import_entry_point(self._install_helper)

    @property
    def dependency_handler_class(self):
        """Return a dependency handler that will work for this distro."""
        return importer.import_entry_point(self._dependency_handler["name"])

    def extract_component(self, name, action, default_entry_point_creator=None):
        """Return the class + component info to use for doing the action w/the component."""
        try:
            # Use a copy instead of the original since we will be
            # modifying this dictionary which may not be wanted for future
            # usages of this dictionary (so keep the original clean)...
            component_info = copy.deepcopy(self._components[name])
        except KeyError:
            component_info = {}
        action_classes = component_info.pop('action_classes', {})
        if default_entry_point_creator is not None:
            default_action_classes = default_entry_point_creator(name,
                                                                 copy.deepcopy(component_info))
            if default_action_classes:
                for (an_action, entry_point) in six.iteritems(default_action_classes):
                    if an_action not in action_classes:
                        action_classes[an_action] = entry_point
        try:
            entry_point = action_classes.pop(action)
        except KeyError:
            raise RuntimeError('No entrypoint configured/generated for'
                               ' %r %r for distribution %r' % (action, name, self.name))
        else:
            return Component(entry_point, component_info, action_classes)


def _match_distros(distros):
    plt = platform.platform()
    matches = []
    for d in distros:
        if d.supports_platform(plt):
            matches.append(d)
    if not matches:
        raise excp.ConfigException('No distro matched for platform %r' % plt)
    else:
        return matches


def load(path):
    distro_possibles = []
    input_files = glob.glob(sh.joinpths(path, '*.yaml'))
    if not input_files:
        raise excp.ConfigException('Did not find any distro definition files in %r' % path)
    for fn in input_files:
        LOG.debug("Attempting to load distro definition from %r", fn)
        try:
            cls_kvs = utils.load_yaml(fn)
        except Exception as err:
            LOG.warning('Could not load distro definition from %r: %s', fn, err)
        else:
            if 'name' not in cls_kvs:
                name, _ext = os.path.splitext(sh.basename(fn))
                cls_kvs['name'] = name
            distro_possibles.append(Distro(**cls_kvs))
    return _match_distros(distro_possibles)
