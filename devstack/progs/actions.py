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


def _pre_run(action_name, root_dir, pkg_manager, config, component_order, all_instances):
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
        base_inst = all_instances[component]
        base_inst.verify()
    LOG.info("Warming up your component configurations (ie so you won't be prompted later)")
    for component in component_order:
        base_inst = all_instances[component]
        base_inst.warm_configs()
    if action_name in _RC_FILE_MAKE_ACTIONS and not loaded_env:
        _gen_localrc(config, _RC_FILE)


def _print_cfgs(config_obj, action):

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


def _instanciate_components(action_name, components, distro, pkg_manager, config, root_dir):
    all_instances = dict()
    for component in components.keys():
        cls = common.get_action_cls(action_name, component, distro)
        instance = cls(instances=all_instances,
                              distro=distro,
                              packager=pkg_manager,
                              config=config,
                              root=root_dir,
                              opts=components.get(component, list()))
        all_instances[component] = instance
    return all_instances


def _gen_localrc(config, fn):
    LOG.info("Generating a file at [%s] that will contain your environment settings." % (fn))
    creator = env_rc.RcGenerator(config)
    contents = creator.generate()
    sh.write_file(fn, contents)


def _run_instances(call_ordering, all_instances, component_order, force):
    LOG.info("Running in the following order: %s" % ("->".join(component_order)))
    for (start_msg, functor, end_msg) in call_ordering:
        for c in component_order:
            instance = all_instances[c]
            if start_msg:
                LOG.info(start_msg.format(name=c))
            result = None
            try:
                result = functor(instance)
            except (excp.NoTraceException) as e:
                if force:
                    LOG.debug("Skipping exception [%s]" % (e))
                else:
                    raise
            if end_msg:
                LOG.info(end_msg.format(name=c, result=result))


def _run_preqs(root_action, component_order, components, distro, root_dir, program_args, config, pkg_manager):
    if root_action == settings.START:
        preq_action = settings.INSTALL
        instances = _instanciate_components(preq_action, components, distro, pkg_manager, config, root_dir)
        adjusted_order = list()
        for c in component_order:
            instance = instances[c]
            if not instance.is_installed():
                adjusted_order.append(c)
        if adjusted_order:
            _run_components(preq_action, adjusted_order, components, distro, root_dir, program_args, config, pkg_manager)
    elif root_action == settings.UNINSTALL:
        preq_action = settings.STOP
        instances = _instanciate_components(preq_action, components, distro, pkg_manager, config, root_dir)
        adjusted_order = list()
        for c in component_order:
            instance = instances[c]
            if instance.is_started():
                adjusted_order.append(c)
        if adjusted_order:
            _run_components(preq_action, adjusted_order, components, distro, root_dir, program_args, config, pkg_manager)


def _apply_reverse(action_name, component_order):
    adjusted_order = list(component_order)
    if action_name in _REVERSE_ACTIONS:
        adjusted_order.reverse()
    return adjusted_order


def _run_components(action_name, component_order, components, distro, root_dir, program_args, config, pkg_manager):
    _run_preqs(action_name, component_order, components, distro, root_dir, program_args, config, pkg_manager)
    LOG.info("Activating components required to complete action [%s]" % (action_name))
    all_instances = _instanciate_components(action_name, components, distro, pkg_manager, config, root_dir)
    _pre_run(action_name, root_dir, pkg_manager, config, component_order, all_instances)
    _run_instances(ACTION_MP[action_name], all_instances, _apply_reverse(action_name, component_order), program_args.get('force', False))


def run(args):

    #input and distro checks
    (distro, platform) = utils.determine_distro()
    if distro is None:
        print("Unsupported platform " + utils.color_text(platform, "red") + "!")
        return False
    defaulted_components = False
    components = utils.parse_components(args.pop("components"))
    if not components:
        defaulted_components = True
        components = common.get_default_components(distro)
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

    #here on out we should be using the logger (and not print)
    if not defaulted_components:
        LOG.info("Activating components [%s]" % (", ".join(sorted(components.keys()))))
    else:
        LOG.info("Activating default components [%s]" % (", ".join(sorted(components.keys()))))

    #determine the runtime order
    ignore_deps = args.pop('ignore_deps', False)
    component_order = None
    if not ignore_deps:
        all_components_deps = common.get_components_deps(action, components, distro, rootdir)
        component_diff = set(all_components_deps.keys()).difference(components.keys())
        if component_diff:
            LOG.info("Having to activate dependent components: [%s]" \
                         % (", ".join(sorted(component_diff))))
            for new_component in component_diff:
                components[new_component] = list()
        component_order = utils.get_components_order(all_components_deps)
    else:
        component_order = components.keys()

    #add in any that will just be referenced but which will not actually do anything (ie the action will not be applied to these)
    ref_components = utils.parse_components(args.pop("ref_components"))
    for c in ref_components.keys():
        if c not in components:
            components[c] = ref_components.get(c)

    LOG.info("Starting action [%s] on %s for distro [%s]" % (action, date.rcf8222date(), distro))
    start_time = time.time()
    config = common.get_config()
    pkg_manager = common.get_packager(distro, args.pop('keep_packages', True))
    _run_components(action, component_order, components, distro, rootdir, args, config, pkg_manager)
    time_taken = (time.time() - start_time)
    LOG.info("It took (%s) to complete action [%s]" % (common.format_secs_taken(time_taken), action))
    _print_cfgs(config, action)

    return True
