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
import os

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
from anvil import type_utils as tu
from anvil import utils

LOG = logging.getLogger(__name__)


class PhaseFunctors(object):
    def __init__(self, start, run, end):
        self.start = start
        self.run = run
        self.end = end


class Action(object):
    __meta__ = abc.ABCMeta

    def __init__(self, name, distro, root_dir, cli_opts):
        self.distro = distro
        self.root_dir = root_dir
        self.name = name
        self.interpolator = cfg.YamlInterpolator(settings.COMPONENT_CONF_DIR)
        self.passwords = {}
        self.keyring_path = cli_opts.pop('keyring_path')
        self.keyring_encrypted = cli_opts.pop('keyring_encrypted')
        self.prompt_for_passwords = cli_opts.pop('prompt_for_passwords', False)
        self.store_passwords = cli_opts.pop('store_passwords', True)
        self.cli_opts = cli_opts # Stored for components to get any options

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
            wanted_passwords = instance.get_option('wanted_passwords') or []
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
        return list(components)

    def _get_component_dirs(self, component):
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

    def _merge_options(self, name, distro_opts, component_opts, persona_opts):
        opts = utils.merge_dicts(self._get_component_dirs(name),
                                 distro_opts, component_opts, persona_opts)
        return opts

    def _merge_subsystems(self, component_subsys, desired_subsys):
        joined_subsys = {}
        if not component_subsys:
            component_subsys = {}
        if not desired_subsys:
            return joined_subsys
        for subsys in desired_subsys:
            if subsys in component_subsys:
                joined_subsys[subsys] = component_subsys[subsys]
            else:
                joined_subsys[subsys] = {}
        return joined_subsys

    def _construct_siblings(self, name, siblings, params, sibling_instances):
        there_siblings = {}
        for (action, cls_name) in siblings.items():
            if action not in sibling_instances:
                sibling_instances[action] = {}
            cls = importer.import_entry_point(cls_name)
            sibling_params = utils.merge_dicts(params, self.cli_opts, preserve=True)
            sibling_params['instances'] = sibling_instances[action]
            LOG.debug("Construction of sibling component %r (%r) params are:", name, action)
            utils.log_object(sibling_params, logger=LOG, level=logging.DEBUG)
            a_sibling = cls(**sibling_params)
            # Update the sibling we are returning and the corresponding
            # siblings for that action (so that the sibling can have the
            # correct 'sibling' instances associated with it, if it needs those...)
            there_siblings[action] = a_sibling
            sibling_instances[action][name] = a_sibling
        return there_siblings

    def _get_interp_options(self, name):
        base = {}
        for c in ['general', name]:
            base.update(self.interpolator.extract(c))
        return base

    def _construct_instances(self, persona):
        """
        Create component objects for each component in the persona.
        """
        persona_subsystems = persona.wanted_subsystems or {}
        persona_opts = persona.component_options or {}
        instances = {}
        sibling_instances = {}
        for c in persona.wanted_components:
            ((cls, distro_opts), siblings) = self.distro.extract_component(c, self.lookup_name)
            LOG.debug("Constructing component %r (%s)", c, tu.obj_name(cls))
            instance_params = {}
            instance_params['name'] = c
            # First create its siblings with a 'minimal' set of options
            # This is done, so that they will work in a minimal state, they do not
            # get access to the persona options since those are action specific (or could be),
            # if this is not useful, we can give them full access, unsure if its worse or better...
            instance_params['subsystems'] = {}
            instance_params['siblings'] = {}
            instance_params['passwords'] = self.passwords
            instance_params['distro'] = self.distro
            instance_params['options'] = self._merge_options(c, self._get_interp_options(c), distro_opts, {})
            LOG.debug("Constructing %r siblings...", c)
            siblings = self._construct_siblings(c, siblings, instance_params, sibling_instances)
            # Now inject the full options
            instance_params['instances'] = instances
            instance_params['options'] = self._merge_options(c, self._get_interp_options(c), distro_opts,
                                                            (persona_opts.get(c) or {}))
            instance_params['subsystems'] = self._merge_subsystems((distro_opts.pop('subsystems', None) or {}),
                                                                   (persona_subsystems.get(c) or {}))
            instance_params['siblings'] = siblings
            instance_params = utils.merge_dicts(instance_params, self.cli_opts, preserve=True)
            LOG.debug("Construction of %r params are:", c)
            utils.log_object(instance_params, logger=LOG, level=logging.DEBUG)
            instances[c] = cls(**instance_params)
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
        self._establish_passwords(component_order, instances)
        self._verify_components(component_order, instances)
        self._warm_components(component_order, instances)

    def _write_exports(self, component_order, instances, path):
        # TODO(harlowja) perhaps remove this since its only used in a subclass...
        pass

    def _on_finish(self, persona, component_order, instances):
        LOG.info("Tearing down your components.")
        LOG.debug("Final environment settings:")
        utils.log_object(env.get(), logger=LOG, level=logging.DEBUG, item_max_len=64)
        exports_filename = "%s.rc" % (self.name)
        self._write_exports(component_order, instances, sh.joinpths("/etc/anvil", exports_filename))

    def _get_phase_directory(self, name=None):
        if not name:
            name = self.name
        return sh.joinpths(self.root_dir, "phases", name)

    def _get_phase_filename(self, phase_name, base_name=None):
        dir_path = self._get_phase_directory(base_name)
        if not sh.isdir(dir_path):
            sh.mkdirslist(dir_path)
        return sh.joinpths(dir_path, "%s.phases" % (phase_name.lower()))

    def _run_phase(self, functors, component_order, instances, phase_name):
        """
        Run a given 'functor' across all of the components, in order.
        """
        component_results = dict()
        if phase_name:
            phase_recorder = phase.PhaseRecorder(self._get_phase_filename(phase_name))
        else:
            phase_recorder = phase.NullPhaseRecorder()

        def change_activate(instance, on_off):
            # Activate/deactivate them and there siblings (if any)
            instance.activated = on_off
            for (_name, sibling_instance) in instance.siblings.items():
                sibling_instance.activated = on_off

        # Reset all activations
        for c in component_order:
            change_activate(instances[c], False)

        # Run all components which have not been ran previously (due to phase tracking)
        for c in component_order:
            instance = instances[c]
            if c in phase_recorder:
                LOG.debug("Skipping phase named %r for component %r since it already happened.", phase_name, c)
                change_activate(instance, True)
                component_results[c] = None
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
                    change_activate(instance, True)
                except excp.NoTraceException:
                    pass
        self._on_completion(phase_name, component_results)
        return component_results

    def _get_opposite_stages(self, phase_name):
        return ('', [])

    def _on_completion(self, phase_name, results):
        (base_name, to_destroy) = self._get_opposite_stages(phase_name)
        for name in to_destroy:
            fn = self._get_phase_filename(name, base_name)
            if sh.isfile(fn):
                sh.unlink(fn)

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
        return component_order
