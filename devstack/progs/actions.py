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

LOG = logging.getLogger("devstack.progs.actions")

# For actions in this list we will reverse the component order
REVERSE_ACTIONS = [settings.UNINSTALL, settings.STOP]

# For these actions we will attempt to make an rc file if it does not exist
RC_FILE_MAKE_ACTIONS = [settings.INSTALL]

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
    def __init__(self, distro, action,
                    cfg, pw_gen, pkg_manager,
                    **kargs):
        self.distro = distro
        self.action = action
        self.cfg = cfg
        self.pw_gen = pw_gen
        self.pkg_manager = pkg_manager
        self.keep_old = kargs.get('keep_old', False)
        self.force = kargs.get('force', False)

    def _apply_reverse(self, action, component_order):
        adjusted_order = list(component_order)
        if action in REVERSE_ACTIONS:
            adjusted_order.reverse()
        return adjusted_order

    def _construct_instances(self, persona, action, root_dir):
        components = persona.wanted_components
        desired_subsystems = persona.wanted_subsystems or dict()
        component_opts = persona.component_options or dict()
        instances = dict()
        for c in components:
            (cls, my_info) = self.distro.extract_component(c, action)
            LOG.debug("Constructing class %s" % (cls))
            cls_kvs = dict()
            cls_kvs['runner'] = self
            cls_kvs['component_dir'] = sh.joinpths(root_dir, c)
            cls_kvs['subsystem_info'] = my_info.get('subsystems') or dict()
            cls_kvs['all_instances'] = instances
            cls_kvs['name'] = c
            cls_kvs['keep_old'] = self.keep_old
            cls_kvs['desired_subsystems'] = desired_subsystems.get(c) or set()
            cls_kvs['options'] = component_opts.get(c) or dict()
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
        LOG.info("Warming up your component configurations (ie so you won't be prompted later)")
        for c in component_order:
            instance = instances[c]
            instance.warm_configs()

    def _write_rc_file(self, root_dir):
        writer = env_rc.RcWriter(self.cfg, self.pw_gen, root_dir)
        if not sh.isfile(settings.OSRC_FN):
            LOG.info("Generating a file at [%s] that will contain your environment settings." % (settings.OSRC_FN))
            writer.write(settings.OSRC_FN)
        else:
            LOG.info("Updating a file at [%s] that contains your environment settings." % (settings.OSRC_FN))
            am_upd = writer.update(settings.OSRC_FN)
            LOG.info("Updated [%s] settings in rc file [%s]" % (am_upd, settings.OSRC_FN))

    def _run_instances(self, action, component_order, instances):
        for (start_msg, functor, end_msg) in ACTION_MP[action]:
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

    def _run_action(self, persona, action, root_dir):
        instances = self._construct_instances(persona, action, root_dir)
        if action in PREQ_ACTIONS:
            (check_functor, preq_action) = PREQ_ACTIONS[action]
            checks_passed_components = list()
            for (c, instance) in instances.items():
                if check_functor(instance):
                    checks_passed_components.append(c)
            if checks_passed_components:
                LOG.info("Activating prerequisite action [%s] requested by (%s) components."
                    % (preq_action, ", ".join(checks_passed_components)))
                self._run_action(persona, preq_action, root_dir)
        component_order = self._apply_reverse(action, persona.wanted_components)
        LOG.info("Activating components [%s] (in that order) for action [%s]" %
                  ("->".join(component_order), action))
        self._verify_components(component_order, instances)
        self._warm_components(component_order, instances)
        if action in RC_FILE_MAKE_ACTIONS:
            self._write_rc_file(root_dir)
        self._run_instances(action, component_order, instances)

    def run(self, persona, root_dir):
        self._run_action(persona, self.action, root_dir)
