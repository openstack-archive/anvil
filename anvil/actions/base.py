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
import copy

from anvil import cfg
from anvil import colorizer
from anvil import env
from anvil import exceptions as excp
from anvil import importer
from anvil import log as logging
from anvil import passwords as pw
from anvil import phase
from anvil import settings
from anvil import shell as sh
from anvil import utils

from anvil.utils import OrderedDict

LOG = logging.getLogger(__name__)

# Include the general yaml during all interpolation
# actions since it typically contains useful shared settings...
BASE_YAML_INTERP = ('general', )


class PhaseFunctors(object):
    def __init__(self, start, run, end):
        self.start = start
        self.run = run
        self.end = end


class Action(object):
    __meta__ = abc.ABCMeta
    needs_sudo = True

    def __init__(self, name, distro, root_dir, cli_opts):
        self.distro = distro
        self.name = name
        # Root directory where all files/downloads will be based at
        self.root_dir = root_dir
        # Action phases are tracked in this directory
        self.phase_dir = sh.joinpths(root_dir, 'phases')
        # Yamls are 'interpolated' using this instance at the given
        # component directory where component configuration will be found...
        self.interpolator = cfg.YamlInterpolator(settings.COMPONENT_CONF_DIR)
        # Keyring/pw settings + cache
        self.passwords = {}
        self.keyring_path = cli_opts.pop('keyring_path')
        self.keyring_encrypted = cli_opts.pop('keyring_encrypted')
        self.prompt_for_passwords = cli_opts.pop('prompt_for_passwords', False)
        self.store_passwords = cli_opts.pop('store_passwords', True)
        # Stored for components to get any options
        self.cli_opts = cli_opts

    def _establish_passwords(self, component_order, instances):
        kr = pw.KeyringProxy(self.keyring_path,
                             self.keyring_encrypted,
                             self.prompt_for_passwords,
                             True)
        LOG.info("Reading passwords using a %s", kr)
        to_save = {}
        self.passwords.clear()
        already_gotten = set()
        for c in component_order:
            instance = instances[c]
            wanted_passwords = instance.get_option('wanted_passwords')
            if not wanted_passwords:
                continue
            for (name, prompt) in wanted_passwords.items():
                if name in already_gotten:
                    continue
                (from_keyring, pw_provided) = kr.read(name, prompt)
                if not from_keyring and self.store_passwords:
                    to_save[name] = pw_provided
                self.passwords[name] = pw_provided
                already_gotten.add(name)
        if to_save:
            LOG.info("Saving %s passwords using a %s", len(to_save), kr)
            for (name, pw_provided) in to_save.items():
                kr.save(name, pw_provided)

    @abc.abstractproperty
    @property
    def lookup_name(self):
        # Name that will be used to lookup this module
        # in any configuration (may or may not be the same as the name
        # of this action)....
        raise NotImplementedError()

    @abc.abstractmethod
    def _run(self, persona, component_order, instances):
        """Run the phases of processing for this action.

        Subclasses are expected to override this method to
        do something useful.
        """
        raise NotImplementedError()

    def _order_components(self, components):
        """Returns the components in the order they should be processed.
        """
        # Duplicate the list to avoid problems if it is updated later.
        return copy.copy(components)

    def _get_component_dirs(self, component):
        component_dir = sh.joinpths(self.root_dir, component)
        trace_dir = sh.joinpths(component_dir, 'traces')
        app_dir = sh.joinpths(component_dir, 'app')
        return {
            'app_dir': app_dir,
            'component_dir': component_dir,
            'root_dir': self.root_dir,
            'trace_dir': trace_dir,
        }

    def _merge_options(self, name, distro_opts, component_opts, persona_opts):
        return utils.merge_dicts(self._get_component_dirs(name),
                                 distro_opts, component_opts, persona_opts)

    def _merge_subsystems(self, distro_subsystems, desired_subsystems):
        subsystems = {}
        for subsystem_name in desired_subsystems:
            # Return a deep copy so that later instances can not modify
            # other instances subsystem accidentally...
            subsystems[subsystem_name] = copy.deepcopy(distro_subsystems.get(subsystem_name, {}))
        return subsystems

    def _construct_siblings(self, name, siblings, base_params, sibling_instances):
        # First setup the sibling instance action references
        for (action, _entry_point) in siblings.items():
            if action not in sibling_instances:
                sibling_instances[action] = {}
        there_siblings = {}
        for (action, entry_point) in siblings.items():
            sibling_params = utils.merge_dicts(base_params, self.cli_opts, preserve=True)
            # Give the sibling the reference to all other siblings being created
            # which will be populated when they are created (now or later) for
            # the same action
            sibling_params['instances'] = sibling_instances[action]
            a_sibling = importer.construct_entry_point(entry_point, **sibling_params)
            # Update the sibling we are returning and the corresponding
            # siblings for that action (so that the sibling can have the
            # correct 'sibling' instances associated with it, if it needs those...)
            there_siblings[action] = a_sibling
            # Update all siblings being constructed so that there siblings will
            # be correct when fetched...
            sibling_instances[action][name] = a_sibling
        return there_siblings

    def _get_interpolated_names(self, name):
        # Return which sources that will be interpolated from
        # Note(harlowja): if one of the bases here pulls in
        # another yaml, it will be done automatically so this
        # list is more of the starting list and not the end list...
        return list(BASE_YAML_INTERP) + [name]

    def _get_interpolated_options(self, name):
        opts = {}
        for c in self._get_interpolated_names(name):
            opts.update(self.interpolator.extract(c))
        return opts

    def _construct_instances(self, persona):
        """Create component objects for each component in the persona."""
        persona_subsystems = persona.wanted_subsystems or {}
        persona_opts = persona.component_options or {}
        wanted_components = persona.wanted_components or []
        # All siblings for the current persona
        instances = {}
        # Keeps track of all sibling instances across all components + actions
        # so that each instance or sibling instance will be connected to the
        # right set of siblings....
        sibling_instances = {}
        for c in wanted_components:
            d_component = self.distro.extract_component(c, self.lookup_name)
            LOG.debug("Constructing component %r (%s)", c, d_component.entry_point)
            d_subsystems = d_component.options.pop('subsystems', {})
            sibling_params = {}
            sibling_params['name'] = c
            # First create its siblings with a 'minimal' set of options
            # This is done, so that they will work in a minimal state, they do not
            # get access to the persona options since those are action specific (or could be),
            # if this is not useful, we can give them full access, unsure if its worse or better...
            active_subsystems = self._merge_subsystems(distro_subsystems=d_subsystems,
                                                       desired_subsystems=persona_subsystems.get(c, []))
            sibling_params['subsystems'] = active_subsystems
            sibling_params['siblings'] = {}  # This gets adjusted during construction
            sibling_params['passwords'] = self.passwords
            sibling_params['distro'] = self.distro
            sibling_params['options'] = self._merge_options(c,
                                                            component_opts=self._get_interpolated_options(c),
                                                            distro_opts=d_component.options,
                                                            persona_opts={})
            LOG.debug("Constructing %r %s siblings...", c, len(d_component.siblings))
            my_siblings = self._construct_siblings(c, d_component.siblings, sibling_params, sibling_instances)
            # Now inject the full options and create the target instance
            # with the full set of options and not the restricted set that
            # siblings get...
            instance_params = dict(sibling_params)
            instance_params['instances'] = instances
            instance_params['options'] = self._merge_options(c,
                                                             component_opts=self._get_interpolated_options(c),
                                                             distro_opts=d_component.options,
                                                             persona_opts=persona_opts.get(c, {}))
            instance_params['siblings'] = my_siblings
            instance_params = utils.merge_dicts(instance_params, self.cli_opts, preserve=True)
            instances[c] = importer.construct_entry_point(d_component.entry_point, **instance_params)
        return instances

    def _verify_components(self, component_order, instances):
        LOG.info("Verifying that the components are ready to rock-n-roll.")
        for c in component_order:
            instances[c].verify()

    def _warm_components(self, component_order, instances):
        LOG.info("Warming up component configurations.")
        for c in component_order:
            instances[c].warm_configs()

    def _on_start(self, persona, component_order, instances):
        LOG.info("Booting up your components.")
        LOG.debug("Starting environment settings:")
        utils.log_object(env.get(), logger=LOG, level=logging.DEBUG, item_max_len=64)
        sh.mkdirslist(self.phase_dir)
        self._establish_passwords(component_order, instances)
        self._verify_components(component_order, instances)
        self._warm_components(component_order, instances)

    def _on_finish(self, persona, component_order, instances):
        LOG.info("Tearing down your components.")
        LOG.debug("Final environment settings:")
        utils.log_object(env.get(), logger=LOG, level=logging.DEBUG, item_max_len=64)

    def _get_phase_filename(self, phase_name):
        # Do some canonicalization of the phase name so its in a semi-standard format...
        phase_name = phase_name.lower().strip()
        phase_name = phase_name.replace("-", '_')
        phase_name = phase_name.replace(" ", "_")
        if not phase_name:
            raise ValueError("Phase name must not be empty")
        return sh.joinpths(self.phase_dir, "%s.phases" % (phase_name))

    def _run_phase(self, functors, component_order, instances, phase_name, *inv_phase_names):
        """Run a given 'functor' across all of the components, in order."""
        # All the results for each component end up in here
        # in the order in which they ran...
        component_results = OrderedDict()

        # This phase recorder will be used to check if a given component
        # and action has ran in the past, if so that components action
        # will not be ran again. It will also be used to mark that a given
        # component has completed a phase (if that phase runs).
        if not phase_name:
            phase_recorder = phase.NullPhaseRecorder()
        else:
            phase_recorder = phase.PhaseRecorder(self._get_phase_filename(phase_name))

        # These phase recorders will be used to undo other actions activities
        # ie, when an install completes you want the uninstall phase to be
        # removed from that actions phase file (and so on). This list will be
        # used to accomplish that.
        neg_phase_recs = []
        if inv_phase_names:
            for n in inv_phase_names:
                if not n:
                    neg_phase_recs.append(phase.NullPhaseRecorder())
                else:
                    neg_phase_recs.append(phase.PhaseRecorder(self._get_phase_filename(n)))

        def change_activate(instance, on_off):
            # Activate/deactivate a component instance and there siblings (if any)
            #
            # This is used when you say are looking at components
            # that have been activated before your component has been.
            #
            # Typically this is useful for checking if a previous component
            # has a shared dependency with your component and if so then there
            # is no need to reinstall said dependency...
            instance.activated = on_off
            for (_name, sibling_instance) in instance.siblings.items():
                sibling_instance.activated = on_off

        def run_inverse_recorders(c_name):
            for n in neg_phase_recs:
                n.unmark(c_name)

        # Reset all activations
        for c in component_order:
            change_activate(instances[c], False)

        # Run all components which have not been ran previously (due to phase tracking)
        for c in component_order:
            result = None
            instance = instances[c]
            if c in phase_recorder:
                LOG.debug("Skipping phase named %r for component %r since it already happened.", phase_name, c)
            else:
                try:
                    with phase_recorder.mark(c):
                        if functors.start:
                            functors.start(instance)
                        if functors.run:
                            result = functors.run(instance)
                        if functors.end:
                            functors.end(instance, result)
                except excp.NoTraceException:
                    pass
            change_activate(instance, True)
            component_results[c] = result
            run_inverse_recorders(c)
        return component_results

    def run(self, persona):
        instances = self._construct_instances(persona)
        component_order = self._order_components(persona.wanted_components)
        LOG.info("Processing components for action %s.", colorizer.quote(self.name))
        utils.log_iterable(component_order,
                           header="Activating in the following order",
                           logger=LOG)
        self._on_start(persona, component_order, instances)
        self._run(persona, component_order, instances)
        self._on_finish(persona, component_order, instances)
