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

from devstack import date
from devstack import env_rc
from devstack import exceptions as excp
from devstack import log as logging
from devstack import packager
from devstack import pip
from devstack import settings
from devstack import shell as sh
from devstack import trace as tr
from devstack import utils


LOG = logging.getLogger("devstack.progs.actions")


class ActionRunner(object):
    __meta__ = abc.ABCMeta
    NAME = None

    def __init__(self,
                 distro,
                 cfg,
                 pw_gen,
                 **kargs):
        self.distro = distro
        self.cfg = cfg
        self.pw_gen = pw_gen
        self.keep_old = kargs.get('keep_old', False)
        self.force = kargs.get('force', False)

    @abc.abstractmethod
    def prerequisite(self):
        return None

    @abc.abstractmethod
    def _instance_needs_prereq(self, instance):
        """Determine if the instance will require our prerequisite to be invoked.

        Return boolean where True means invoke the prerequisite.
        """
        return False

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

    def get_component_dirs(self, root_dir, component):
        component_dir = sh.joinpths(root_dir, component)
        trace_dir = sh.joinpths(component_dir, settings.COMPONENT_TRACE_DIR)
        app_dir = sh.joinpths(component_dir, settings.COMPONENT_APP_DIR)
        cfg_dir = sh.joinpths(component_dir, settings.COMPONENT_CONFIG_DIR)
        return {
            'component_dir': component_dir,
            'trace_dir': trace_dir,
            'app_dir': app_dir,
            'cfg_dir': cfg_dir,
        }

    def _construct_instances(self, persona, root_dir):
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
            (cls, my_info) = self.distro.extract_component(c, self.NAME)
            LOG.debug("Constructing class %s" % (cls))
            cls_kvs = {}
            cls_kvs['runner'] = self
            cls_kvs.update(self.get_component_dirs(root_dir, c))
            cls_kvs['subsystem_info'] = my_info.get('subsystems', {})
            cls_kvs['all_instances'] = instances
            cls_kvs['name'] = c
            cls_kvs['keep_old'] = self.keep_old
            cls_kvs['desired_subsystems'] = desired_subsystems.get(c, set())
            cls_kvs['options'] = component_opts.get(c, {})
            cls_kvs['pip_factory'] = pip_factory
            cls_kvs['packager_factory'] = pkg_factory
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

    def _get_phase_dir(self, instance):
        return instance.trace_dir

    def _skip_phase(self, instance, mark):
        phase_fn = "%s.phases" % (self.NAME)
        trace_fn = tr.trace_fn(self._get_phase_dir(instance), phase_fn)
        LOG.debug("Checking if we already completed phase %r by looking in %r", mark, trace_fn)
        reader = tr.TraceReader(trace_fn)
        skipable = False
        try:
            marks = reader.marks_made()
            for mark_found in marks:
                if mark == mark_found.get('id'):
                    skipable = True
                    LOG.debug("Completed phase %r on: %s", mark, mark_found.get('when'))
                    break
        except excp.NoTraceException:
            pass
        return skipable

    def _mark_phase(self, instance, mark):
        phase_fn = "%s.phases" % (self.NAME)
        trace_fn = tr.trace_fn(self._get_phase_dir(instance), phase_fn)
        writer = tr.TraceWriter(trace_fn, break_if_there=False)
        LOG.debug("Marking we completed phase %r in file %r", mark, trace_fn)
        details = {
            'id': mark,
            'when': date.rcf8222date(),
        }
        writer.mark(details)

    def _run_phase(self, start_msg, functor, end_msg, component_order, instances, phase_name):
        """
        Run a given 'functor' across all of the components, in order.
        """
        for c in component_order:
            instance = instances[c]
            if self._skip_phase(instance, phase_name):
                LOG.debug("Skipping phase named %r for component %r", phase_name, c)
            else:
                LOG.info(start_msg.format(name=c))
                try:
                    result = functor(instance)
                    LOG.info(end_msg.format(name=c, result=result))
                    self._mark_phase(instance, phase_name)
                except (excp.NoTraceException) as e:
                    if self.force:
                        LOG.debug("Skipping exception [%s]" % (e))
                    else:
                        raise

    def _delete_phase_files(self, instance, names):
        phase_dir = self._get_phase_dir(instance)
        for name in names:
            phase_fn = "%s.phases" % (name)
            sh.unlink(tr.trace_fn(phase_dir, phase_fn))

    def _handle_prereq(self, persona, instances, root_dir):
        preq_cls = self.prerequisite()
        if not preq_cls:
            return
        components_needing_prereq = []
        for (c, instance) in instances.items():
            if self._instance_needs_prereq(instance):
                components_needing_prereq.append(c)
        preq_cls_name = preq_cls.NAME or "???"
        if components_needing_prereq:
            LOG.info("Processing prerequisite action %r requested by (%s) components.",
                        preq_cls_name, ", ".join(components_needing_prereq))
            prereq_instance = preq_cls(self.distro,
                                    self.cfg,
                                    self.pw_gen,
                                    keep_old=self.keep_old,
                                    force=self.force
                                 )
            prereq_instance.run(persona, root_dir)

    def run(self, persona, root_dir):
        instances = self._construct_instances(persona, root_dir)
        self._handle_prereq(persona, instances, root_dir)
        component_order = self._order_components(persona.wanted_components)
        LOG.info("Processing components for action %r", (self.NAME or "???"))
        utils.log_iterable(component_order,
                        header="Activating in the following order:",
                        logger=LOG)
        self._verify_components(component_order, instances)
        self._warm_components(component_order, instances)
        self._run(persona, root_dir, component_order, instances)


class InstallRunner(ActionRunner):

    NAME = 'install'

    def _instance_needs_prereq(self, instance):
        return False

    def _write_rc_file(self, root_dir):
        fn = sh.abspth(settings.gen_rc_filename('core'))
        writer = env_rc.RcWriter(self.cfg, self.pw_gen, root_dir)
        if not sh.isfile(fn):
            LOG.info("Generating a file at %r that will contain your environment settings.", fn)
            writer.write(fn)
        else:
            LOG.info("Updating a file at %r that contains your environment settings.", fn)
            am_upd = writer.update(fn)
            LOG.info("Updated %s settings in rc file %r", am_upd, fn)

    def _run(self, persona, root_dir, component_order, instances):
        self._write_rc_file(root_dir)
        self._run_phase(
            'Downloading {name}',
            lambda i: i.download(),
            "Performed {result} downloads.",
            component_order,
            instances,
            "Download"
            )
        self._run_phase(
            'Configuring {name}',
            lambda i: i.configure(),
            "Configured {result} items.",
            component_order,
            instances,
            "Configure"
            )
        self._run_phase(
            'Pre-installing {name}',
            lambda i: i.pre_install(),
            "Finished pre-install of {name}",
            component_order,
            instances,
            "Pre-install"
            )
        self._run_phase(
            'Installing {name}',
            lambda i: i.install(),
            "Finished install of {name} - check {result} for information on what was done.",
            component_order,
            instances,
            "Install"
            )
        self._run_phase(
            'Post-installing {name}',
            lambda i: i.post_install(),
            "Finished post-install of {name}",
            component_order,
            instances,
            "Post-install"
            )


class StartRunner(ActionRunner):

    NAME = 'running'

    def _instance_needs_prereq(self, instance):
        return not instance.is_installed()

    def prerequisite(self):
        return InstallRunner

    def _run(self, persona, root_dir, component_order, instances):
        self._run_phase(
            'Configuring runner for {name}',
            lambda i: i.configure(),
            "Finished configuring runner for {name}",
            component_order,
            instances,
            "Configure"
            )
        self._run_phase(
            'Pre-starting {name}',
            lambda i: i.pre_start(),
            "Finished pre-start of {name}",
            component_order,
            instances,
            "Pre-start"
            )
        self._run_phase(
            'Starting {name}',
            lambda i: i.start(),
            "Started {result} applications",
            component_order,
            instances,
            "Start"
            )
        self._run_phase(
            'Post-starting {name}',
            lambda i: i.post_start(),
            "Finished post-start of {name}",
            component_order,
            instances,
            "Post-start"
            )


class StopRunner(ActionRunner):

    NAME = 'running'

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
            "Stopped"
            )
        for i in instances.values():
            self._delete_phase_files(i, set([self.NAME, StartRunner.NAME]))


class UninstallRunner(ActionRunner):

    NAME = 'uninstall'

    def prerequisite(self):
        return StopRunner

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
            "Finished unconfiguring of {name}",
            component_order,
            instances,
            "Unconfigure"
            )
        self._run_phase(
            'Pre-uninstalling {name}',
            lambda i: i.pre_uninstall(),
            "Finished pre-uninstall of {name}",
            component_order,
            instances,
            "Pre-uninstall"
            )
        self._run_phase(
            'Uninstalling {name}',
            lambda i: i.uninstall(),
            "Finished uninstall of {name}",
            component_order,
            instances,
            "Uninstall"
            )
        self._run_phase(
            'Post-uninstalling {name}',
            lambda i: i.post_uninstall(),
            "Finished post-uninstall of {name}",
            component_order,
            instances,
            "Post-uninstall"
            )
        for i in instances.values():
            self._delete_phase_files(i, set([self.NAME, InstallRunner.NAME]))


_NAMES_TO_RUNNER = {
    'install': InstallRunner,
    'uninstall': UninstallRunner,
    'start': StartRunner,
    'stop': StopRunner,
}


def get_action_names():
    """
    Returns a list of the available action names.
    """
    return sorted(_NAMES_TO_RUNNER.keys())


def get_runner_factory(action):
    """
    Given an action name, look up the factory for that action runner.
    """
    try:
        return _NAMES_TO_RUNNER[action]
    except KeyError:
        raise ValueError('Unrecognized action %s' % action)
