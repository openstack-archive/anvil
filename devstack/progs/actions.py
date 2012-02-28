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

import time

from devstack import date
from devstack import env_rc
from devstack import exceptions as excp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

from devstack.progs import common

LOG = logging.getLogger("devstack.progs.actions")

# This is used to map an action to a useful string for
# the welcome display
_WELCOME_MAP = {
    settings.INSTALL: "INSTALLER",
    settings.UNINSTALL: "UNINSTALLER",
    settings.START: "STARTER",
    settings.STOP: "STOPPER",
}

# For actions in this list we will reverse the component order
_REVERSE_ACTIONS = [settings.UNINSTALL, settings.STOP]

# For these actions we will attempt to make an rc file if it does not exist
_RC_FILE_MAKE_ACTIONS = [settings.INSTALL, settings.START]
_RC_FILE = sh.abspth(settings.OSRC_FN)

# The order of which uninstalls happen + message of what is happening (before and after)
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

# The order of which starts happen + message of what is happening (before and after)
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

# The order of which stops happen + message of what is happening (before and after)
STOPS_ORDERING = [
     (
         "Stopping {name}.",
         (lambda instance:(instance.stop())),
         "Stopped {result} items.",
     ),
]

# The order of which install happen + message of what is happening (before and after)
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

# These actions must have there prerequisite action accomplished (if determined by the boolean lambda to be needed)
PREQ_ACTIONS = {
    settings.START: ((lambda instance: (not instance.is_installed())), settings.INSTALL),
    settings.UNINSTALL: ((lambda instance: (instance.is_started())), settings.STOP),
}


class ActionRunner(object):
    def __init__(self, distro, action, directory, config, pkg_manager, **kargs):
        self.distro = distro
        self.action = action
        self.directory = directory
        self.cfg = config
        self.pkg_manager = pkg_manager
        self.kargs = kargs
        self.components = kargs.pop("components")
        self.force = kargs.get('force', False)
        self.ignore_deps = kargs.get('ignore_deps', False)
        self.ref_components = kargs.get("ref_components")

    def _get_components(self):
        components = self.components
        if not components:
            components = common.get_default_components(self.distro)
            LOG.info("Activating default components [%s]" % (", ".join(sorted(components.keys()))))
        else:
            LOG.info("Activating components [%s]" % (", ".join(sorted(components.keys()))))
        return components

    def _order_components(self, components):
        adjusted_components = dict(components)
        if self.ignore_deps:
            return (adjusted_components, list(components.keys()))
        all_components = common.get_components_deps(self.action, components, self.distro, self.directory)
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
            instance = cls(instances=all_instances,
                                  distro=self.distro,
                                  packager=self.pkg_manager,
                                  config=self.cfg,
                                  root=self.directory,
                                  opts=components.get(component, list()))
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
        loaded_env = False
        try:
            if sh.isfile(_RC_FILE):
                LOG.info("Attempting to load rc file at [%s] which has your environment settings." % (_RC_FILE))
                am_loaded = env_rc.RcLoader().load(_RC_FILE)
                loaded_env = True
                LOG.info("Loaded [%s] settings from rc file [%s]" % (am_loaded, _RC_FILE))
        except IOError:
            LOG.warn('Error reading rc file located at [%s]. Skipping loading it.' % (_RC_FILE))
        LOG.info("Verifying that the components are ready to rock-n-roll.")
        for component in component_order:
            inst = instances[component]
            inst.verify()
        LOG.info("Warming up your component configurations (ie so you won't be prompted later)")
        for component in component_order:
            inst = instances[component]
            inst.warm_configs()
        if self.action in _RC_FILE_MAKE_ACTIONS and not loaded_env:
            self._gen_localrc(_RC_FILE)

    def _run_instances(self, instances, component_order):
        component_order = self._apply_reverse(component_order)
        LOG.info("Running in the following order: %s" % ("->".join(component_order)))
        for (start_msg, functor, end_msg) in ACTION_MP[self.action]:
            for c in component_order:
                instance = instances[c]
                if start_msg:
                    LOG.info(start_msg.format(name=c))
                result = None
                try:
                    result = functor(instance)
                except (excp.NoTraceException) as e:
                    if self.force:
                        LOG.debug("Skipping exception [%s]" % (e))
                    else:
                        raise
                if end_msg:
                    LOG.info(end_msg.format(name=c, result=result))

    def _apply_reverse(self, component_order):
        adjusted_order = list(component_order)
        if self.action in _REVERSE_ACTIONS:
            adjusted_order.reverse()
        return adjusted_order

    def _gen_localrc(self, fn):
        LOG.info("Generating a file at [%s] that will contain your environment settings." % (fn))
        creator = env_rc.RcGenerator(self.cfg)
        contents = creator.generate()
        sh.write_file(fn, contents)

    def _start(self, components, component_order):
        LOG.info("Activating components required to complete action [%s]" % (self.action))
        instances = self._instanciate_components(components)
        self._pre_run(instances, component_order)
        self._run_preqs(components, component_order)
        self._run_instances(instances, component_order)

    def run(self):
        (components, component_order) = self._order_components(self._get_components())
        self._start(self._inject_references(components), component_order)


def _dump_cfgs(config_obj, action):

    def item_format(key, value):
        return "\t%s=%s" % (str(key), str(value))

    def map_print(mp):
        for key in sorted(mp.keys()):
            value = mp.get(key)
            LOG.info(item_format(key, value))

    passwords_gotten = config_obj.pws
    full_cfgs = config_obj.configs_fetched
    db_dsns = config_obj.db_dsns
    if passwords_gotten or full_cfgs or db_dsns:
        LOG.info("After action [%s] your settings which were created or read are:" % (action))
        if passwords_gotten:
            LOG.info("Passwords:")
            map_print(passwords_gotten)
        if full_cfgs:
            filtered = dict((k, v) for (k, v) in full_cfgs.items() if k not in passwords_gotten)
            if filtered:
                LOG.info("Configs:")
                map_print(filtered)
        if db_dsns:
            LOG.info("Data source names:")
            map_print(db_dsns)


def run(args):

    (distro, platform) = utils.determine_distro()
    if distro is None:
        print("Unsupported platform " + utils.color_text(platform, "red") + "!")
        return False

    action = args.pop("action", "").strip().lower()
    if not (action in settings.ACTIONS):
        print(utils.color_text("No valid action specified!", "red"))
        return False

    rootdir = args.pop("dir")
    if not rootdir:
        print(utils.color_text("No root directory specified!", "red"))
        return False

    (rep, maxlen) = utils.welcome(_WELCOME_MAP.get(action))
    print(utils.center_text("Action Runner", rep, maxlen))

    start_time = time.time()
    config = common.get_config()
    pkg_manager = common.get_packager(distro, args.pop('keep_packages', True))
    runner = ActionRunner(distro, action, rootdir, config, pkg_manager, **args)
    LOG.info("Starting action [%s] on %s for distro [%s]" % (action, date.rcf8222date(), distro))
    runner.run()
    LOG.info("It took (%s) to complete action [%s]" % (common.format_secs_taken((time.time() - start_time)), action))
    _dump_cfgs(config, action)

    return True
