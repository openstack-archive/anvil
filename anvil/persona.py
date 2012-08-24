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

import yaml

from anvil import log as logging

LOG = logging.getLogger(__name__)


class Persona(object):

    def __init__(self, supports, components, **kargs):
        self.distro_support = supports or []
        self.wanted_components = components or []
        self.source = kargs.get('source')
        self.wanted_subsystems = kargs.get('subsystems') or {}
        self.component_options = kargs.get('options') or {}

    def verify(self, distro):
        # Some sanity checks against the given distro/persona
        d_name = distro.name
        if d_name not in self.distro_support:
            raise RuntimeError("Persona does not support the loaded distro")
        for c in self.wanted_components:
            if not distro.known_component(c):
                raise RuntimeError("Persona provided component %s but its not supported by the loaded distro" % (c))


def load(fn):
    # Don't use sh here so that we always
    # read this (even if dry-run)
    with open(fn, 'r') as fh:
        contents = fh.read()
    cls_kvs = yaml.safe_load(contents)
    cls_kvs['source'] = fn
    instance = Persona(**cls_kvs)
    return instance
