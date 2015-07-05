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

import six

from anvil import colorizer
from anvil import log as logging
from anvil import utils

LOG = logging.getLogger(__name__)
SPECIAL_GROUPS = frozenset(['general'])


class Persona(object):

    def __init__(self, supports, components, **kwargs):
        self.distro_support = supports or []
        self.source = kwargs.pop('source', None)
        self.wanted_components = utils.group_builds(components)
        self.wanted_subsystems = kwargs.pop('subsystems', {})
        self.component_options = kwargs.pop('options', {})
        self.no_origins = kwargs.pop('no-origin', [])
        self.matched_components = []
        self.distro_updates = kwargs

    def match(self, distros, origins):
        for group in self.wanted_components:
            for c in group:
                if c not in origins:
                    if c in self.no_origins:
                        LOG.debug("Automatically enabling component %s, not"
                                  " present in origins file %s but present in"
                                  " desired persona %s (origin not required).",
                                  c, origins.filename, self.source)
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
        self.matched_components = []
        all_components = set()
        for group in self.wanted_components:
            adjusted_group = utils.Group(group.id)
            for c in group:
                if c not in disabled_components:
                    adjusted_group.append(c)
                    all_components.add(c)
            if adjusted_group:
                for c in SPECIAL_GROUPS:
                    if c not in adjusted_group:
                        adjusted_group.insert(0, c)
                        all_components.add(c)
                self.matched_components.append(adjusted_group)

        # Pick which of potentially many distros will work...
        distro_names = set()
        selected_distro = None
        for distro in distros:
            distro_names.add(distro.name)
            if distro.name not in self.distro_support:
                continue
            will_work = True
            for component in all_components:
                if not distro.known_component(component):
                    will_work = False
                    LOG.warning("Persona specified component '%s' but"
                                " distro '%s' does not specify it", component,
                                distro.name)
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
