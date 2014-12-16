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

import jsonpatch

import six

from anvil import colorizer
from anvil import log as logging
from anvil import utils

LOG = logging.getLogger(__name__)
SPECIAL_GROUPS = frozenset(['general'])


class Persona(object):

    def __init__(self, supports, components, **kargs):
        self.distro_support = supports or []
        self.source = kargs.get('source')
        self.wanted_components = utils.group_builds(components)
        self.wanted_subsystems = kargs.get('subsystems') or {}
        self.component_options = kargs.get('options') or {}
        self.no_origins = kargs.get('no-origin') or []

    def match(self, distros, origins_fn, origins_patch=None):
        # Filter out components that are disabled in origins file
        origins = utils.load_yaml(origins_fn)
        # Apply any user specified patches to origins file
        if origins_patch:
            patch = jsonpatch.JsonPatch(origins_patch)
            patch.apply(origins, in_place=True)
        for group in self.wanted_components:
            for c in group:
                if c not in origins:
                    if c in self.no_origins:
                        LOG.debug("Automatically enabling component %s, not"
                                  " present in origins file %s but present in"
                                  " desired persona %s (origin not required).",
                                  c, origins_fn, self.source)
                        origins[c] = {
                            'disabled': False,
                        }
                    else:
                        LOG.warn("Automatically disabling %s, not present in"
                                 " origin file but present in desired"
                                 " persona (origin required).",
                                 colorizer.quote(c, quote_color='red'))
                        origins[c] = {
                            'disabled': True,
                        }
        disabled_components = set(key
                                  for key, value in six.iteritems(origins)
                                  if value.get('disabled'))
        wanted_components = []
        all_wanted_components = set()
        for component_group in self.wanted_components:
            adjusted_group = utils.Group(component_group.group)
            for c in component_group:
                if c not in disabled_components:
                    adjusted_group.append(c)
                    all_wanted_components.add(c)
            if adjusted_group:
                for c in SPECIAL_GROUPS:
                    if c not in adjusted_group:
                        adjusted_group.insert(0, c)
                        all_wanted_components.add(c)
                wanted_components.append(adjusted_group)
        self.wanted_components = wanted_components

        # Pick which of potentially many distros will work...
        distro_names = set()
        selected_distro = None
        for distro in distros:
            distro_names.add(distro.name)
            if distro.name not in self.distro_support:
                continue
            will_work = True
            for component in all_wanted_components:
                if not distro.known_component(component):
                    will_work = False
                    break
            if will_work:
                selected_distro = distro
                break
        if selected_distro is None:
            raise RuntimeError("Persona does not support any of the loaded"
                               " distros: %s" % list(distro_names))
        else:
            return selected_distro


def load(fn):
    cls_kvs = utils.load_yaml(fn)
    cls_kvs['source'] = fn
    instance = Persona(**cls_kvs)
    return instance
