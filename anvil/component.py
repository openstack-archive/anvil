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

import functools
import pkg_resources
import re
import weakref

from anvil import colorizer
from anvil import constants
from anvil import downloader as down
from anvil import exceptions as excp
from anvil import importer
from anvil import log as logging
from anvil import packager
from anvil import pip
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils


LOG = logging.getLogger(__name__)


class Component(object):
    def __init__(self,
                 subsystems,
                 runner,
                 instances,
                 options,
                 name,
                 siblings,
                 *args,
                 **kargs):

        # Subsystems this was requested with
        self.subsystems = subsystems
        
        # The component name (from config)
        self.name = name
        
        # Any component options
        self.options = options

        # All the other active instances
        self.instances = instances

        # All the other class names that can be used alongside this class
        self.siblings = siblings

        # The runner has a reference to us, so use a weakref here to
        # avoid breaking garbage collection.
        self.runner = weakref.proxy(runner)

        # Parts of the global runner context that we use
        self.cfg = runner.cfg
        
        # The distribution 'interaction object'
        self.distro = runner.distro

        # Turned on and off as phases get activated
        self.activated = False

    def get_option(self, opt_name, def_val=None):
        return self.options.get(opt_name, def_val)

    @property
    def env_exports(self):
        return {}

    def verify(self):
        # Ensure subsystems are 'valid'...
        for s in self.subsystems:
            if s not in self.valid_subsystems:
                raise ValueError("Unknown subsystem %r requested for component: %s" % (s, self))

    def __str__(self):
        return "%s@%s" % (self.__class__.__name__, self.name)

    @property
    def params(self):
        # Various params that are frequently accessed
        return {
            'APP_DIR': self.get_option('app_dir'),
            'COMPONENT_DIR': self.get_option('component_dir'),
            'CONFIG_DIR': self.get_option('cfg_dir'),
            'TRACE_DIR': self.get_option('trace_dir'),
        }

    def _get_trace_files(self):
        trace_dir = self.get_option('trace_dir')
        return {
            'install': tr.trace_fn(trace_dir, "install"),
            'start': tr.trace_fn(trace_dir, "start"),
        }

    @property
    def valid_subsystems(self):
        return []

    def warm_configs(self):
        # Before any actions occur you get the chance to 
        # warmup the configs u might use (ie for prompting for passwords
        # earlier rather than later
        pass
