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
from anvil import date
from anvil import env_rc
from anvil import exceptions as excp
from anvil import log as logging
from anvil import packager
from anvil import pip
from anvil import settings
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils


LOG = logging.getLogger(__name__)


PhaseFunctors = collections.namedtuple('PhaseFunctors', ['start', 'run', 'end'])


class ActionRunner(object):
    __meta__ = abc.ABCMeta
    NAME = None

    def __init__(self,
                 distro,
                 cfg,
                 pw_gen,
                 root_dir,
                 **kargs):
        self.distro = distro
        self.cfg = cfg
        self.pw_gen = pw_gen
        self.keep_old = kargs.get('keep_old', False)
        self.force = kargs.get('force', False)
        self.root_dir = root_dir

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
            (cls, my_info) = self.distro.extract_component(c, self.NAME)
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

    def _skip_phase(self, instance, mark):
        phase_fn = "%s.phases" % (self.NAME)
        trace_fn = tr.trace_fn(self.root_dir, phase_fn)
        name = instance.component_name
        LOG.debug("Checking if we already completed phase %r by looking in %r for component %s", mark, trace_fn, name)
        skipable = False
        try:
            reader = tr.TraceReader(trace_fn)
            marks = reader.marks_made()
            for mark_found in marks:
                if mark == mark_found.get('id') and name == mark_found.get('name'):
                    skipable = True
                    LOG.debug("Completed phase %r on for component %s: %s", mark, mark_found.get('name'), mark_found.get('when'))
                    break
        except excp.NoTraceException:
            pass
        return skipable

    def _mark_phase(self, instance, mark):
        phase_fn = "%s.phases" % (self.NAME)
        trace_fn = tr.trace_fn(self.root_dir, phase_fn)
        name = instance.component_name
        writer = tr.TraceWriter(trace_fn, break_if_there=False)
        LOG.debug("Marking we completed phase %r in file %r for component %s", mark, trace_fn, name)
        details = {
            'id': mark,
            'when': date.rcf8222date(),
            'name': name,
        }
        writer.mark(details)

    def _run_phase(self, functors, component_order, instances, phase_name):
        """
        Run a given 'functor' across all of the components, in order.
        """
        component_results = dict()
        for c in component_order:
            instance = instances[c]
            if self._skip_phase(instance, phase_name):
                LOG.debug("Skipping phase named %r for component %r", phase_name, c)
            else:
                try:
                    if functors.start:
                        functors.start(instance)
                    result = None
                    if functors.run:
                        result = functors.run(instance)
                    if functors.end:
                        functors.end(instance, result)
                    component_results[instance] = result
                    self._mark_phase(instance, phase_name)
                except (excp.NoTraceException) as e:
                    if self.force:
                        LOG.debug("Skipping exception: %s" % (e))
                    else:
                        raise
        return component_results

    def _delete_phase_files(self, names):
        phase_dir = self.root_dir
        for name in names:
            sh.unlink(tr.trace_fn(phase_dir, "%s.phases" % (name)))

    def _handle_prereq(self, persona, instances):
        preq_cls = self.prerequisite()
        if not preq_cls:
            return
        components_needing_prereq = []
        for (c, instance) in instances.items():
            if self._instance_needs_prereq(instance):
                components_needing_prereq.append(c)
        preq_cls_name = preq_cls.NAME or "???"
        if components_needing_prereq:
            utils.log_iterable(components_needing_prereq, logger=LOG,
                header="Processing prerequisite action %s requested by" % colorizer.quote(preq_cls_name))
            prereq_instance = preq_cls(self.distro,
                                    self.cfg,
                                    self.pw_gen,
                                    keep_old=self.keep_old,
                                    force=self.force,
                                    root_dir=self.root_dir,
                                 )
            prereq_instance.run(persona)

    def run(self, persona):
        instances = self._construct_instances(persona)
        self._handle_prereq(persona, instances)
        component_order = self._order_components(persona.wanted_components)
        LOG.info("Processing components for action %s.", colorizer.quote(self.NAME or "???"))
        utils.log_iterable(component_order,
                        header="Activating in the following order",
                        logger=LOG)
        self._verify_components(component_order, instances)
        self._warm_components(component_order, instances)
        self._run(persona, component_order, instances)


class InstallRunner(ActionRunner):

    NAME = 'install'

    def _instance_needs_prereq(self, instance):
        return False

    def _write_rc_file(self):
        fn = sh.abspth(settings.gen_rc_filename('core'))
        writer = env_rc.RcWriter(self.cfg, self.pw_gen, self.root_dir)
        if not sh.isfile(fn):
            LOG.info("Generating a file at %s that will contain your environment settings.", colorizer.quote(fn))
            writer.write(fn)
        else:
            LOG.info("Updating a file at %s that contains your environment settings.", colorizer.quote(fn))
            am_upd = writer.update(fn)
            LOG.info("Updated %s settings.", colorizer.quote(am_upd))

    def _run(self, persona, component_order, instances):
        self._write_rc_file()
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Downloading %s.', colorizer.quote(i.component_name)),
                run=lambda i: i.download(),
                end=lambda i, result: LOG.info("Performed %s downloads.", result),
            ),
            component_order,
            instances,
            "Download"
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Configuring %s.', colorizer.quote(i.component_name)),
                run=lambda i: i.configure(),
                end=lambda i, result: LOG.info("Configured %s items.", colorizer.quote(result)),
            ),
            component_order,
            instances,
            "Configure"
            )
        self._run_phase(
            PhaseFunctors(
                start=None,
                run=lambda i: i.pre_install(),
                end=None,
            ),
            component_order,
            instances,
            "Pre-install"
            )

        def install_start(instance):
            subsystems = set(list(instance.desired_subsystems))
            if subsystems:
                utils.log_iterable(subsystems, logger=LOG,
                    header='Installing %s using subsystems' % colorizer.quote(instance.component_name))
            else:
                LOG.info("Installing %s.", colorizer.quote(instance.component_name))

        self._run_phase(
            PhaseFunctors(
                start=install_start,
                run=lambda i: i.install(),
                end=(lambda i, result: LOG.info("Finished install of %s items - check %s for information on what was done.",
                        colorizer.quote(i.component_name), colorizer.quote(result))),
            ),
            component_order,
            instances,
            "Install"
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Post-installing %s.', colorizer.quote(i.component_name)),
                run=lambda i: i.post_install(),
                end=None
            ),
            component_order,
            instances,
            "Post-install",
            )


class StartRunner(ActionRunner):

    NAME = 'running'

    def _instance_needs_prereq(self, instance):
        return not instance.is_installed()

    def prerequisite(self):
        return InstallRunner

    def _run(self, persona, component_order, instances):
        self._run_phase(
            PhaseFunctors(
                start=None,
                run=lambda i: i.configure(),
                end=None,
            ),
            component_order,
            instances,
            "Configure",
            )
        self._run_phase(
            PhaseFunctors(
                start=None,
                run=lambda i: i.pre_start(),
                end=None,
            ),
            component_order,
            instances,
            "Pre-start",
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Starting %s.', i.component_name),
                run=lambda i: i.start(),
                end=lambda i, result: LOG.info("Start %s applications", colorizer.quote(result)),
            ),
            component_order,
            instances,
            "Start"
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Post-starting %s.', colorizer.quote(i.component_name)),
                run=lambda i: i.post_start(),
                end=None,
            ),
            component_order,
            instances,
            "Post-start",
            )


class StopRunner(ActionRunner):

    NAME = 'running'

    def _instance_needs_prereq(self, instance):
        return False

    def _order_components(self, components):
        components = super(StopRunner, self)._order_components(components)
        components.reverse()
        return components

    def _run(self, persona, component_order, instances):
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Stopping %s.', colorizer.quote(i.component_name)),
                run=lambda i: i.stop(),
                end=lambda i, result: LOG.info("Stopped %s items.", colorizer.quote(result)),
            ),
            component_order,
            instances,
            "Stopped"
            )
        self._delete_phase_files(set([self.NAME, StartRunner.NAME]))


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

    def _run(self, persona, component_order, instances):
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Unconfiguring %s.', colorizer.quote(i.component_name)),
                run=lambda i: i.unconfigure(),
                end=None,
            ),
            component_order,
            instances,
            "Unconfigure"
            )
        self._run_phase(
            PhaseFunctors(
                start=None,
                run=lambda i: i.pre_uninstall(),
                end=None,
            ),
            component_order,
            instances,
            "Pre-uninstall",
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Uninstalling %s.', colorizer.quote(i.component_name)),
                run=lambda i: i.uninstall(),
                end=None,
            ),
            component_order,
            instances,
            "Uninstall"
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Post-uninstalling %s.', colorizer.quote(i.component_name)),
                run=lambda i: i.post_uninstall(),
                end=None,
            ),
            component_order,
            instances,
            "Post-uninstall",
            )
        self._delete_phase_files(set([self.NAME, InstallRunner.NAME]))


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
