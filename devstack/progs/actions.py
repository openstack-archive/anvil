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

from devstack import env_rc
from devstack import exceptions as excp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

from devstack.progs import common

LOG = logging.getLogger("devstack.progs.actions")

# For actions in this list we will reverse the component order
_REVERSE_ACTIONS = [settings.UNINSTALL, settings.STOP]

# For these actions we will attempt to make an rc file if it does not exist
_RC_FILE_MAKE_ACTIONS = [settings.INSTALL]

# The order of which uninstalls happen + message of what is happening
# (before and after)
UNINSTALL_ORDERING = [
     (
         "Unconfiguring {name}.",
         (lambda instance: (instance.unconfigure())),
         None,
     ),
     (
         "Pre-uninstalling {name}.",
         (lambda instance: (instance.pre_uninstall())),
         None,
     ),
     (
         "Uninstalling {name}.",
         (lambda instance: (instance.uninstall())),
         None,
     ),
     (
         "Post-uninstalling {name}.",
         (lambda instance: (instance.post_uninstall())),
         None,
     ),
]

# The order of which starts happen + message of what is happening
# (before and after)
STARTS_ORDERING = [
     (
        "Configuring runner for {name}.",
        (lambda instance: (instance.configure())),
        None,
     ),
     (
        "Pre-starting {name}.",
        (lambda instance: (instance.pre_start())),
        None,
     ),
     (
        "Starting {name}.",
        (lambda instance: (instance.start())),
        "Started {result} applications.",
     ),
     (
        "Post-starting {name}.",
        (lambda instance:(instance.post_start())),
        None,
     ),
]

# The order of which stops happen + message of what is happening
# (before and after)
STOPS_ORDERING = [
     (
         "Stopping {name}.",
         (lambda instance:(instance.stop())),
         "Stopped {result} items.",
     ),
]

# The order of which install happen + message of what is happening
# (before and after)
INSTALL_ORDERING = [
    (
        "Downloading {name}.",
        (lambda instance: (instance.download())),
        "Performed {result} downloads.",
    ),
    (
        "Configuring {name}.",
        (lambda instance: (instance.configure())),
        "Configured {result} items.",
    ),
    (
        "Pre-installing {name}.",
        (lambda instance: (instance.pre_install())),
        None,
    ),
    (
        "Installing {name}.",
        (lambda instance: (instance.install())),
        "Finished install of {name} - check {result} for traces of what happened.",
    ),
    (
        "Post-installing {name}.",
        (lambda instance: (instance.post_install())),
        None,
    ),
]

# Map of action name to action order
ACTION_MP = {
    settings.START: STARTS_ORDERING,
    settings.STOP: STOPS_ORDERING,
    settings.INSTALL: INSTALL_ORDERING,
    settings.UNINSTALL: UNINSTALL_ORDERING,
}

# These actions must have there prerequisite action accomplished (if
# determined by the boolean lambda to be needed)
PREQ_ACTIONS = {
    settings.START: ((lambda instance: (not instance.is_installed())), settings.INSTALL),
    settings.UNINSTALL: ((lambda instance: (instance.is_started())), settings.STOP),
}


class ActionRunner(object):
    def __init__(self, distro, action, directory, config,
                 password_generator, pkg_manager,
                 **kargs):
        self.distro = distro
        self.action = action
        self.directory = directory
        self.cfg = config
        self.password_generator = password_generator
        self.pkg_manager = pkg_manager
        self.kargs = kargs
        self.components = dict()
        def_components = common.get_default_components()
        unclean_components = kargs.pop("components")
        if not unclean_components:
            self.components = def_components
        else:
            for (c, opts) in unclean_components.items():
                if opts is None and c in def_components:
                    self.components[c] = def_components[c]
                elif opts is None:
                    self.components[c] = list()
                else:
                    self.components[c] = opts
        self.force = kargs.get('force', False)
        self.ignore_deps = kargs.get('ignore_deps', False)
        self.ref_components = kargs.get("ref_components")
        self.rc_file = sh.abspth(settings.OSRC_FN)
        self.gen_rc = action in _RC_FILE_MAKE_ACTIONS

    def _get_components(self):
        return dict(self.components)

    def _order_components(self, components):
        adjusted_components = dict(components)
        if self.ignore_deps:
            return (adjusted_components, list(components.keys()))
        all_components = common.get_components_deps(
            runner=self,
            action_name=self.action,
            base_components=components,
            root_dir=self.directory,
            distro=self.distro,
            )
        component_diff = set(all_components.keys()).difference(components.keys())
        if component_diff:
            LOG.info("Having to activate dependent components: [%s]" % (", ".join(sorted(component_diff))))
            for new_component in component_diff:
                adjusted_components[new_component] = list()
        return (adjusted_components, utils.get_components_order(all_components))

    def _inject_references(self, components):
        ref_components = utils.parse_components(self.ref_components)
        adjusted_components = dict(components)
        for c in ref_components.keys():
            if c not in components:
                adjusted_components[c] = ref_components.get(c)
        return adjusted_components

    def _instanciate_components(self, components):
        all_instances = dict()
        for component in components.keys():
            cls = common.get_action_cls(self.action, component, self.distro)
            # FIXME: Instead of passing some of these options,
            # pass a reference to the runner itself and let
            # the component keep a weakref to it.
            instance = cls(instances=all_instances,
                           runner=self,
                           root=self.directory,
                           opts=components.get(component, list()),
                           keep_old=self.kargs.get("keep_old")
                           )
            all_instances[component] = instance
        return all_instances

    def _run_preqs(self, components, component_order):
        if not (self.action in PREQ_ACTIONS):
            return
        (check_functor, preq_action) = PREQ_ACTIONS[self.action]
        instances = self._instanciate_components(components)
        preq_components = dict()
        for c in component_order:
            instance = instances[c]
            if check_functor(instance):
                preq_components[c] = components[c]
        if preq_components:
            LOG.info("Having to activate prerequisite action [%s] for %s components." % (preq_action, len(preq_components)))
            preq_runner = ActionRunner(self.distro, preq_action,
                                    self.directory, self.cfg, self.pkg_manager,
                                    components=preq_components, **self.kargs)
            preq_runner.run()

    def _pre_run(self, instances, component_order):
        if not sh.isdir(self.directory):
            sh.mkdir(self.directory)
        if self.rc_file:
            try:
                LOG.info("Attempting to load rc file at [%s] which has your environment settings." % (self.rc_file))
                am_loaded = env_rc.RcReader().load(self.rc_file)
                LOG.info("Loaded [%s] settings from rc file [%s]" % (am_loaded, self.rc_file))
            except IOError:
                LOG.warn('Error reading rc file located at [%s]. Skipping loading it.' % (self.rc_file))
        LOG.info("Verifying that the components are ready to rock-n-roll.")
        for component in component_order:
            inst = instances[component]
            inst.verify()
        LOG.info("Warming up your component configurations (ie so you won't be prompted later)")
        for component in component_order:
            inst = instances[component]
            inst.warm_configs()
        if self.gen_rc and self.rc_file:
            writer = env_rc.RcWriter(self.cfg, self.password_generator)
            if not sh.isfile(self.rc_file):
                LOG.info("Generating a file at [%s] that will contain your environment settings." % (self.rc_file))
                writer.write(self.rc_file)
            else:
                LOG.info("Updating a file at [%s] that contains your environment settings." % (self.rc_file))
                am_upd = writer.update(self.rc_file)
                LOG.info("Updated [%s] settings in rc file [%s]" % (am_upd, self.rc_file))

    def _run_instances(self, instances, component_order):
        component_order = self._apply_reverse(component_order)
        LOG.info("Running in the following order: %s" % ("->".join(component_order)))
        for (start_msg, functor, end_msg) in ACTION_MP[self.action]:
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

    def _apply_reverse(self, component_order):
        adjusted_order = list(component_order)
        if self.action in _REVERSE_ACTIONS:
            adjusted_order.reverse()
        return adjusted_order

    def _start(self, components, component_order):
        LOG.info("Activating components required to complete action [%s]" % (self.action))
        instances = self._instanciate_components(components)
        self._pre_run(instances, component_order)
        self._run_preqs(components, component_order)
        self._run_instances(instances, component_order)

    def run(self):
        (components, component_order) = self._order_components(self._get_components())
        self._start(self._inject_references(components), component_order)
