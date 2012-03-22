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

from devstack import env_rc
from devstack import exceptions as excp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh

LOG = logging.getLogger("devstack.progs.actions")


class ActionRunner(object):
    __meta__ = abc.ABCMeta

    PREREQ = None
    NAME = None

    def __init__(self,
                 distro,
                 cfg,
                 pw_gen,
                 pkg_manager,
                 **kargs):
        self.distro = distro
        self.cfg = cfg
        self.pw_gen = pw_gen
        self.pkg_manager = pkg_manager
        self.keep_old = kargs.get('keep_old', False)
        self.force = kargs.get('force', False)

    @abc.abstractmethod
    def _instance_needs_prereq(self, instance):
        """Determine if the instance will require our prereq to be invoked.

        Return boolean where True means invoke the prereq.
        """
        return

    @abc.abstractmethod
    def _run(self, persona, root_dir, component_order, instances):
        """Run the phases of processing for this action.

        Subclasses are expected to override this method to
        do something useful.
        """

    def _order_components(self, components):
        """Returns the components in the order they should be processed.
        """
        # Duplicate the list to avoid problems if it is updated later.
        return components[:]

    def _construct_instances(self, persona, root_dir):
        """Create component objects for each component in the persona.
        """
        components = persona.wanted_components
        desired_subsystems = persona.wanted_subsystems or {}
        component_opts = persona.component_options or {}
        instances = {}
        for c in components:
            (cls, my_info) = self.distro.extract_component(c, self.NAME)
            LOG.debug("Constructing class %s" % (cls))
            cls_kvs = {}
            cls_kvs['runner'] = self
            cls_kvs['component_dir'] = sh.joinpths(root_dir, c)
            cls_kvs['subsystem_info'] = my_info.get('subsystems', {})
            cls_kvs['all_instances'] = instances
            cls_kvs['name'] = c
            cls_kvs['keep_old'] = self.keep_old
            cls_kvs['desired_subsystems'] = desired_subsystems.get(c, set())
            cls_kvs['options'] = component_opts.get(c, {})
            # The above is not overrideable...
            for (k, v) in my_info.items():
                if k not in cls_kvs:
                    cls_kvs[k] = v
            instances[c] = cls(**cls_kvs)
        return instances

    def _verify_components(self, component_order, instances):
        LOG.info("Verifying that the components are ready to rock-n-roll.")
        for c in component_order:
            instance = instances[c]
            instance.verify()

    def _warm_components(self, component_order, instances):
        LOG.info("Warming up component configurations")
        for c in component_order:
            instance = instances[c]
            instance.warm_configs()

    def _run_phase(self, start_msg, functor, end_msg, component_order, instances):
        """Run a given 'functor' across all of the components, in order.
        """
        for c in component_order:
            instance = instances[c]
            if start_msg:
                LOG.info(start_msg.format(name=c))
            try:
                result = functor(instance)
                if end_msg:
                    LOG.info(end_msg.format(name=c, result=result))
            except (excp.NoTraceException) as e:
                if self.force:
                    LOG.debug("Skipping exception [%s]" % (e))
                else:
                    raise

    def _handle_prereq(self, persona, instances, root_dir):
        if not self.PREREQ:
            return
        components_needing_prereq = [
            c
            for (c, instance) in instances.items()
            if self._instance_needs_prereq(instance)
            ]
        if components_needing_prereq:
            LOG.info("Processing prerequisite action [%s] requested by (%s) components.",
                     self.PREREQ.NAME, ", ".join(components_needing_prereq))
            prereq = self.PREREQ(self.distro,
                                 self.cfg,
                                 self.pw_gen,
                                 self.pkg_manager,
                                 keep_old=self.keep_old,
                                 force=self.force,
                                 )
            prereq.run(persona, root_dir)

    def run(self, persona, root_dir):
        instances = self._construct_instances(persona, root_dir)
        self._handle_prereq(persona, instances, root_dir)
        component_order = self._order_components(persona.wanted_components)
        LOG.info("Processing components [%s] (in that order) for action [%s]",
                 "->".join(component_order), self.NAME)
        self._verify_components(component_order, instances)
        self._warm_components(component_order, instances)
        self._run(persona, root_dir, component_order, instances)
        return


class InstallRunner(ActionRunner):
    NAME = 'install'

    def _instance_needs_prereq(self, instance):
        return False

    def _write_rc_file(self, root_dir):
        writer = env_rc.RcWriter(self.cfg, self.pw_gen, root_dir)
        if not sh.isfile(settings.OSRC_FN):
            LOG.info("Generating a file at [%s] that will contain your environment settings.",
                     settings.OSRC_FN)
            writer.write(settings.OSRC_FN)
        else:
            LOG.info("Updating a file at [%s] that contains your environment settings.",
                     settings.OSRC_FN)
            am_upd = writer.update(settings.OSRC_FN)
            LOG.info("Updated [%s] settings in rc file [%s]",
                     am_upd, settings.OSRC_FN)

    def _run(self, persona, root_dir, component_order, instances):
        self._write_rc_file(root_dir)
        self._run_phase(
            'Downloading {name}',
            lambda i: i.download(),
            "Performed {result} downloads.",
            component_order,
            instances,
            )
        self._run_phase(
            'Configuring {name}',
            lambda i: i.configure(),
            "Configured {result} items.",
            component_order,
            instances,
            )
        self._run_phase(
            'Pre-installing {name}',
            lambda i: i.pre_install(),
            None,
            component_order,
            instances,
            )
        self._run_phase(
            'Installing {name}',
            lambda i: i.install(),
            "Finished install of {name} - check {result} for traces of what happened.",
            component_order,
            instances,
            )
        self._run_phase(
            'Post-installing {name}',
            lambda i: i.post_install(),
            None,
            component_order,
            instances,
            )


class StartRunner(ActionRunner):
    NAME = 'start'
    PREREQ = InstallRunner

    def _instance_needs_prereq(self, instance):
        return not instance.is_installed()

    def _run(self, persona, root_dir, component_order, instances):
        self._run_phase(
            'Configuring runner for {name}',
            lambda i: i.configure(),
            None,
            component_order,
            instances,
            )
        self._run_phase(
            'Pre-starting {name}',
            lambda i: i.pre_start(),
            None,
            component_order,
            instances,
            )
        self._run_phase(
            'Starting {name}',
            lambda i: i.start(),
            "Started {result} applications.",
            component_order,
            instances,
            )
        self._run_phase(
            'Post-starting {name}',
            lambda i: i.post_start(),
            None,
            component_order,
            instances,
            )


class StopRunner(ActionRunner):
    NAME = 'stop'

    def _instance_needs_prereq(self, instance):
        return False

    def _order_components(self, components):
        components = super(StopRunner, self)._order_components(components)
        components.reverse()
        return components

    def _run(self, persona, root_dir, component_order, instances):
        self._run_phase(
            'Stopping {name}',
            lambda i: i.stop(),
            'Stopped {result} items',
            component_order,
            instances,
            )


class UninstallRunner(ActionRunner):
    NAME = 'uninstall'
    PREREQ = StopRunner

    def _instance_needs_prereq(self, instance):
        return instance.is_started()

    def _order_components(self, components):
        components = super(UninstallRunner, self)._order_components(components)
        components.reverse()
        return components

    def _run(self, persona, root_dir, component_order, instances):
        self._run_phase(
            'Unconfiguring {name}',
            lambda i: i.unconfigure(),
            None,
            component_order,
            instances,
            )
        self._run_phase(
            'Pre-uninstalling {name}',
            lambda i: i.pre_uninstall(),
            None,
            component_order,
            instances,
            )
        self._run_phase(
            'Uninstalling {name}',
            lambda i: i.uninstall(),
            None,
            component_order,
            instances,
            )
        self._run_phase(
            'Post-uninstalling {name}',
            lambda i: i.post_uninstall(),
            None,
            component_order,
            instances,
            )


_NAMES_TO_RUNNER = {
    'install': InstallRunner,
    'uninstall': UninstallRunner,
    'start': StartRunner,
    'stop': StopRunner,
    }


def get_action_names():
    """Returns a list of the available action names.
    """
    return sorted(_NAMES_TO_RUNNER.keys())


def get_runner_factory(action):
    """Given an action name, look up the factory for that action runner.
    """
    try:
        return _NAMES_TO_RUNNER[action]
    except KeyError:
        raise ValueError('Unrecognized action %s' % action)
