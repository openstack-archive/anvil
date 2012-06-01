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

import glob
import platform
import re
import shlex

import yaml
import copy

from anvil import colorizer
from anvil import importer
from anvil import log as logging
from anvil import settings
from anvil import shell as sh

LOG = logging.getLogger(__name__)


class Distro(object):

    @classmethod
    def load_all(cls, path=settings.DISTRO_DIR):
        """Returns a list of the known distros."""
        results = []
        input_files = glob.glob(sh.joinpths(path, '*.yaml'))
        if not input_files:
            raise RuntimeError(
                'Did not find any distro definition files in %r' %
                path)
        for fn in input_files:
            cls_kvs = None
            filename = sh.abspth(fn)
            LOG.audit("Attempting to load distro definition from %r" % (filename))
            try:
                with open(filename, 'r') as f:
                    cls_kvs = yaml.load(f)
            except (IOError, yaml.YAMLError) as err:
                LOG.warning('Could not load distro definition from %r: %s',
                            filename, err)
            if cls_kvs is not None:
                try:
                    results.append(cls(**cls_kvs))
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
            raise RuntimeError('Unsupported linux (?) platform %r' % plt)
        LOG.debug('Looking for distro data for %r (%s)', plt, distname)
        for p in cls.load_all():
            if p.supports_distro(plt):
                LOG.info('Using distro %s for platform %s', colorizer.quote(p.name), colorizer.quote(plt))
                return p
        else:
            raise RuntimeError(
                'No platform configuration data for %r (%s)' %
                (plt, distname))

    def __init__(self, name, distro_pattern, packager_name, commands, components):
        self.name = name
        self._distro_pattern = re.compile(distro_pattern, re.IGNORECASE)
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
        LOG.debug("Running over keys (%s)" % (", ".join(run_over_keys)))
        LOG.debug("End key is (%s)" % (end_key))
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
        LOG.debug("Retrieved end command config: %s", end_value)
        return end_value

    def get_command(self, key, *more_keys, **kargs):
        """Retrieves a string for running a command from the setup
        and splits it to return a list.
        """
        val = self.get_command_config(key, *more_keys, **kargs)
        ret_val = shlex.split(val) if val else []
        LOG.debug("Parsed configured command: %s", ret_val)
        return ret_val

    def known_component(self, name):
        return name in self._components

    def supports_distro(self, distro_name):
        """Does this distro support the named Linux distro?

        :param distro_name: Return value from platform.linux_distribution().
        """
        return bool(self._distro_pattern.search(distro_name))

    def get_default_package_manager_cls(self):
        """Return a package manager that will work for this distro."""
        return importer.import_entry_point(self._packager_name)

    def extract_component(self, name, action):
        """Return the class + component info to use for doing the action w/the component."""
        try:
            # Use a copy instead of the original
            component_info = copy.deepcopy(self._components[name])
            entry_point = component_info['action_classes'][action]
            cls = importer.import_entry_point(entry_point)
            # Remove action class info
            if 'action_classes' in component_info:
                del component_info['action_classes']
            return (cls, component_info)
        except KeyError:
            raise RuntimeError('No class configured to %r %r on %r' %
                               (action, name, self.name))
