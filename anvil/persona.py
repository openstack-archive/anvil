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

from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh

LOG = logging.getLogger(__name__)


class Persona(object):

    def __init__(self, description,
                       supports,
                       components,
                       subsystems,
                       options,
                       **kargs):
        self.distro_support = supports
        self.wanted_components = components
        self.source = kargs.get('source')  # May not always be there (ie if from a stream...)
        self.wanted_subsystems = subsystems
        self.description = description
        self.component_options = options

    def __str__(self):
        info = "%s" % (self.description)
        if self.source:
            info += " from source %s:" % (self.source)
        if self.wanted_subsystems:
            info += " with desired subsystems (%s)" % (self.wanted_subsystems)
        if self.wanted_components:
            info += " with desired components (%s)" % (", ".join(self.wanted_components))
        if self.component_options:
            info += " with desired component options (%s)" % (", ".join(self.component_options))
        if self.distro_support:
            info += " which 'should' work on distros (%s)" % (", ".join(self.distro_support))
        return info

    def verify(self, distro):
        # Some sanity checks against the given distro
        d_name = distro.name
        if d_name not in self.distro_support:
            return False
        for c in self.wanted_components:
            if not distro.known_component(c):
                return False
        return True


def load(fn):
    cls_kvs = yaml.load(sh.load_file(fn))
    cls_kvs['source'] = fn
    instance = Persona(**cls_kvs)
    return instance
