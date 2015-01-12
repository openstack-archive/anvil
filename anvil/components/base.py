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

from anvil import exceptions as excp
from anvil import log as logging
from anvil import patcher
from anvil import settings
from anvil import shell as sh
from anvil import trace as tr
from anvil import type_utils as tu
from anvil import utils

LOG = logging.getLogger(__name__)


class Component(object):
    def __init__(self, name, subsystems, instances, options, siblings, distro, **kwargs):
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

        # The distribution 'interaction object'
        self.distro = distro

        # Turned on and off as phases get activated
        self.activated = False

        # Where our binaries will be located
        self.bin_dir = "/usr/bin/"

        # Where configuration will be written
        self.cfg_dir = sh.joinpths("/etc/", self.name)

    def get_password(self, option):
        pw_val = self.passwords.get(option)
        if pw_val is None:
            raise excp.PasswordException("Password asked for option %s but none was pre-populated!" % (option))
        return pw_val

    def get_option(self, option, *options, **kwargs):
        option_value = utils.get_deep(self.options, [option] + list(options))
        if option_value is None:
            return kwargs.get('default_value')
        else:
            return option_value

    def get_bool_option(self, option, *options, **kwargs):
        if 'default_value' not in kwargs:
            kwargs['default_value'] = False
        return tu.make_bool(self.get_option(option, *options, **kwargs))

    def get_int_option(self, option, *options, **kwargs):
        if 'default_value' not in kwargs:
            kwargs['default_value'] = 0
        return int(self.get_option(option, *options, **kwargs))

    @property
    def env_exports(self):
        return {}

    def verify(self):
        pass

    def __str__(self):
        return "%s@%s" % (tu.obj_name(self), self.name)

    @property
    def params(self):
        # Various params that are frequently accessed
        return {
            'APP_DIR': self.get_option('app_dir'),
            'COMPONENT_DIR': self.get_option('component_dir'),
            'TRACE_DIR': self.get_option('trace_dir'),
        }

    def warm_configs(self):
        # Before any actions occur you get the chance to
        # warmup the configs u might use (ie for prompting for passwords
        # earlier rather than later)
        pass

    def subsystem_names(self):
        return self.subsystems.keys()

    @property
    def packages(self):
        return []

    def package_names(self):
        """Return a set of names of all packages for this component."""
        names = set()
        for pack in self.packages:
            try:
                names.add(pack["name"])
            except KeyError:
                pass
        daemon_to_package = self.get_option("daemon_to_package")
        if not daemon_to_package:
            daemon_to_package = {}
        for key in self.subsystem_names():
            try:
                names.add(daemon_to_package[key])
            except KeyError:
                names.add("openstack-%s-%s" % (self.name, key))
        return names


class BasicComponent(Component):
    def __init__(self, *args, **kargs):
        super(BasicComponent, self).__init__(*args, **kargs)
        trace_fn = tr.trace_filename(self.get_option('trace_dir'), 'created')
        self.tracewriter = tr.TraceWriter(trace_fn, break_if_there=False)

    def download(self):
        return []

    def list_patches(self, section):
        what_patches = self.get_option('patches', section)
        if not what_patches:
            what_patches = [sh.joinpths(settings.CONFIG_DIR, 'patches',
                                        self.name, section)]
        canon_what_patches = []
        for path in what_patches:
            if sh.isdir(path):
                patches = sorted(fn for fn in sh.listdir(path, files_only=True)
                                 if fn.endswith('patch'))
                canon_what_patches.extend(patches)
            elif sh.isfile(path):
                canon_what_patches.append(path)
        return canon_what_patches

    def patch(self, section):
        canon_what_patches = self.list_patches(section)
        if canon_what_patches:
            target_dir = self.get_option('app_dir')
            patcher.apply_patches(canon_what_patches, target_dir)
