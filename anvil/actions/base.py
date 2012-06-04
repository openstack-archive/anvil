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

from anvil import colorizer
from anvil import exceptions as excp
from anvil import log as logging
from anvil import phase
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
        raise NotImplementedError()

    @staticmethod
    def get_action_name():
        raise NotImplementedError()

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
        p_subsystems = persona.wanted_subsystems or {}
        p_opts = persona.component_options or {}
        instances = {}
        for c in persona.wanted_components:
            ((cls, opts), siblings) = self.distro.extract_component(c, self.get_lookup_name())
            LOG.debug("Constructing class %s" % (cls))
            cls_kvs = {}
            cls_kvs['runner'] = self
            cls_kvs['siblings'] = siblings
            # Merge subsystems info with wanted subsystems
            sub_systems = {}
            if opts.get('subsystems'):
                sub_systems.update(opts.get('subsystems'))
                del opts['subsystems']
            desired_subs = p_subsystems.get(c) or []
            merged_sub_systems = {}
            for d in desired_subs:
                if d in sub_systems:
                    merged_sub_systems[d] = sub_systems[d]
                else:
                    merged_sub_systems[d] = {}
            cls_kvs['subsystems'] = merged_sub_systems
            cls_kvs['instances'] = instances
            cls_kvs['name'] = c
            # Merge options with keep old
            options = {}
            options['keep_old'] = self.keep_old
            options.update(self.get_component_dirs(c))
            merge_options = p_opts.get(c) or {}
            options.update(merge_options)
            # The above is not overrideable... (except for options key)
            for (k, v) in opts.items():
                if k not in cls_kvs:
                    cls_kvs[k] = v
                elif k == 'options':
                    options.update(v)
                else:
                    LOG.warn("You can not override component constructor variable named %s.", colorizer.quote(k))
            cls_kvs['options'] = options
            LOG.debug("Construction of %r params are %s", c, cls_kvs)
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

    def _get_phase_dir(self, action_name=None):
        if not action_name:
            action_name = self.get_action_name()
        return sh.joinpths(self.root_dir, "phases", action_name)

    def _get_phase_fn(self, phase_name):
        dirname = self._get_phase_dir()
        sh.mkdirslist(dirname)
        return sh.joinpths(dirname, "%s.phases" % (phase_name.lower()))

    def _run_phase(self, functors, component_order, instances, phase_name):
        """
        Run a given 'functor' across all of the components, in order.
        """
        component_results = dict()
        if phase_name:
            phase_recorder = phase.PhaseRecorder(self._get_phase_fn(phase_name))
        else:
            phase_recorder = phase.NullPhaseRecorder()
        for c in component_order:
            instance = instances[c]
            if phase_recorder.has_ran(c):
                LOG.debug("Skipping phase named %r for component %r since it already happened.", phase_name, c)
            else:
                try:
                    result = None
                    with phase_recorder.mark(c):
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

    def _delete_phase_files(self, action_names):
        for n in action_names:
            sh.deldir(self._get_phase_dir(n))

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
