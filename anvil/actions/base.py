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
#    under the License..

import abc
import collections
import glob

from anvil import colorizer
from anvil import exceptions as excp
from anvil import log as logging
from anvil import packager
from anvil import phase
from anvil import pip
from anvil import shell as sh
from anvil import utils

LOG = logging.getLogger(__name__)


PhaseFunctors = collections.namedtuple('PhaseFunctors', ['start', 'run', 'end'])


class Action(object):
    __meta__ = abc.ABCMeta

    def __init__(self, distro, cfg, root_dir, **kargs):
        self.distro = distro
        self.cfg = cfg
        self.keep_old = kargs.get('keep_old', False)
        self.force = kargs.get('force', False)
        self.root_dir = root_dir

    @staticmethod
    def get_lookup_name():
        return None

    @staticmethod
    def get_action_name():
        return None

    @abc.abstractmethod
    def _run(self, persona, component_order, instances):
        """Run the phases of processing for this action.

        Subclasses are expected to override this method to
        do something useful.
        """

    def _order_components(self, components):
        """Returns the components in the order they should be processed.
        """
        # Duplicate the list to avoid problems if it is updated later.
        return list(components)

    def get_component_dirs(self, component):
        component_dir = sh.joinpths(self.root_dir, component)
        trace_dir = sh.joinpths(component_dir, 'traces')
        app_dir = sh.joinpths(component_dir, 'app')
        cfg_dir = sh.joinpths(component_dir, 'config')
        return {
            'app_dir': app_dir,
            'cfg_dir': cfg_dir,
            'component_dir': component_dir,
            'root_dir': self.root_dir,
            'trace_dir': trace_dir,
        }

    def _construct_instances(self, persona):
        """
        Create component objects for each component in the persona.
        """
        components = persona.wanted_components
        desired_subsystems = persona.wanted_subsystems or {}
        component_opts = persona.component_options or {}
        instances = {}
        pip_factory = packager.PackagerFactory(self.distro, pip.Packager)
        pkg_factory = packager.PackagerFactory(self.distro, self.distro.get_default_package_manager_cls())
        for c in components:
            (cls, my_info) = self.distro.extract_component(c, self.get_lookup_name())
            LOG.debug("Constructing class %s" % (cls))
            cls_kvs = {}
            cls_kvs['runner'] = self
            cls_kvs.update(self.get_component_dirs(c))
            cls_kvs['subsystem_info'] = my_info.get('subsystems') or {}
            cls_kvs['all_instances'] = instances
            cls_kvs['name'] = c
            cls_kvs['keep_old'] = self.keep_old
            cls_kvs['desired_subsystems'] = desired_subsystems.get(c) or set()
            cls_kvs['options'] = component_opts.get(c) or {}
            cls_kvs['pip_factory'] = pip_factory
            cls_kvs['packager_factory'] = pkg_factory
            # The above is not overrideable...
            for (k, v) in my_info.items():
                if k not in cls_kvs:
                    cls_kvs[k] = v
                else:
                    LOG.warn("You can not override component constructor variable named %s.", colorizer.quote(k))
            instances[c] = cls(**cls_kvs)
        return instances

    def _verify_components(self, component_order, instances):
        LOG.info("Verifying that the components are ready to rock-n-roll.")
        for c in component_order:
            instances[c].verify()

    def _warm_components(self, component_order, instances):
        LOG.info("Warming up component configurations.")
        for c in component_order:
            instances[c].warm_configs()

    def _run_phase(self, functors, component_order, instances, phase_name):
        """
        Run a given 'functor' across all of the components, in order.
        """
        component_results = dict()
        phase_recorder = None
        if phase_name:
            phase_fn = "%s.%s.phases" % (self.get_action_name(), phase_name.lower())
            phase_recorder = phase.PhaseRecorder(sh.joinpths(self.root_dir, phase_fn))
        for c in component_order:
            instance = instances[c]
            if phase_recorder and phase_recorder.has_ran(instance.component_name):
                LOG.debug("Skipping phase named %r for component %r since it already happened.", phase_name, c)
            else:
                try:
                    result = None
                    if phase_recorder:
                        with phase_recorder.mark(instance.component_name):
                            if functors.start:
                                functors.start(instance)
                            if functors.run:
                                result = functors.run(instance)
                            if functors.end:
                                functors.end(instance, result)
                    else:
                        if functors.start:
                            functors.start(instance)
                        if functors.run:
                            result = functors.run(instance)
                        if functors.end:
                            functors.end(instance, result)
                    component_results[instance] = result
                except (excp.NoTraceException) as e:
                    if self.force:
                        LOG.debug("Skipping exception: %s" % (e))
                    else:
                        raise
        return component_results

    def _delete_phase_files(self, names):
        for n in names:
            phases_path = sh.joinpths(self.root_dir, '%s.*.phases' % (n))
            for fn in glob.glob(phases_path):
                if sh.isfile(fn):
                    sh.unlink(fn)

    def run(self, persona):
        instances = self._construct_instances(persona)
        component_order = self._order_components(persona.wanted_components)
        LOG.info("Processing components for action %s.", colorizer.quote(self.get_action_name()))
        utils.log_iterable(component_order,
                        header="Activating in the following order",
                        logger=LOG)
        self._verify_components(component_order, instances)
        self._warm_components(component_order, instances)
        self._run(persona, component_order, instances)
        return component_order
