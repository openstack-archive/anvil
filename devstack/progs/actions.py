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

from devstack import cfg
from devstack import date
from devstack import exceptions as excp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

from devstack.packaging import apt
from devstack.packaging import yum

from devstack.progs import common

LOG = logging.getLogger("devstack.progs.actions")

#this map controls which distro has
#which package management class
_PKGR_MAP = {
    settings.UBUNTU11: apt.AptPackager,
    settings.RHEL6: yum.YumPackager,
}

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

# These will not automatically stop when uninstalled since it seems to break there password reset.
_NO_AUTO_STOP = [settings.DB, settings.RABBIT]


def _clean_action(action):
    if action is None:
        return None
    action = action.strip().lower()
    if not (action in settings.ACTIONS):
        return None
    return action


def _get_pkg_manager(distro, keep_packages):
    cls = _PKGR_MAP.get(distro)
    return cls(distro, keep_packages)


def _check_roots(action, rootdir, components):
    #TODO the check is really pretty basic so should not be depended on...
    to_skip = list()
    if action == settings.INSTALL:
        if sh.isdir(rootdir):
            to_skip = list()
            for c in components:
                check_pth = sh.joinpths(rootdir, c)
                if sh.isdir(check_pth) and len(sh.listdir(check_pth)) != 0:
                    LOG.warn("Component directory [%s] already exists and its not empty (skipping installing that component)!" % check_pth)
                    LOG.warn("If this is undesired please remove it or uninstall %s!" % (c))
                    to_skip.append(c)
    return to_skip


def _pre_run(action_name, **kargs):
    if action_name == settings.INSTALL:
        root_dir = kargs.get("root_dir")
        if root_dir:
            sh.mkdir(root_dir)


def _post_run(action_name, **kargs):
    if action_name == settings.UNINSTALL:
        root_dir = kargs.get("root_dir")
        if root_dir:
            sh.rmdir(root_dir)


def _print_cfgs(config_obj, action):

    #this will make the items nice and pretty
    def item_format(key, value):
        return "\t%s=%s" % (str(key), str(value))

    def map_print(mp):
        for key in sorted(mp.keys()):
            value = mp.get(key)
            LOG.info(item_format(key, value))

    #now make it pretty
    passwords_gotten = config_obj.pws
    full_cfgs = config_obj.configs_fetched
    db_dsns = config_obj.db_dsns
    if passwords_gotten or full_cfgs or db_dsns:
        LOG.info("After action (%s) your settings are:" % (action))
        if passwords_gotten:
            LOG.info("Passwords:")
            map_print(passwords_gotten)
        if full_cfgs:
            #TODO
            #better way to do this?? (ie a list difference?)
            filtered_mp = dict()
            for key in full_cfgs.keys():
                if key in passwords_gotten:
                    continue
                filtered_mp[key] = full_cfgs.get(key)
            if filtered_mp:
                LOG.info("Configs:")
                map_print(filtered_mp)
        if db_dsns:
            LOG.info("Data source names:")
            map_print(db_dsns)


def _install(component_name, instance):
    LOG.info("Downloading %s." % (component_name))
    am_downloaded = instance.download()
    LOG.info("Performed %s downloads." % (am_downloaded))
    LOG.info("Configuring %s." % (component_name))
    am_configured = instance.configure()
    LOG.info("Configured %s items." % (am_configured))
    LOG.info("Pre-installing %s." % (component_name))
    instance.pre_install()
    LOG.info("Installing %s." % (component_name))
    instance.install()
    LOG.info("Post-installing %s." % (component_name))
    trace = instance.post_install()
    if trace:
        LOG.info("Finished install of %s - check %s for traces of what happened." % (component_name, trace))
    else:
        LOG.info("Finished install of %s" % (component_name))
    return trace


def _stop(component_name, instance, skip_notrace):
    try:
        LOG.info("Stopping %s." % (component_name))
        stop_amount = instance.stop()
        LOG.info("Stopped %s items." % (stop_amount))
        LOG.info("Finished stop of %s" % (component_name))
    except excp.NoTraceException, e:
        if skip_notrace:
            LOG.info("Passing on stopping %s since no trace file was found." % (component_name))
        else:
            raise


def _start(component_name, instance):
    LOG.info("Pre-starting %s." % (component_name))
    instance.pre_start()
    LOG.info("Starting %s." % (component_name))
    start_info = instance.start()
    LOG.info("Post-starting %s." % (component_name))
    instance.post_start()
    if type(start_info) == list:
        LOG.info("Check [%s] for traces of what happened." % (", ".join(start_info)))
    elif type(start_info) == int:
        LOG.info("Started %s applications." % (start_info))
        start_info = None
    LOG.info("Finished start of %s." % (component_name))
    return start_info


def _uninstall(component_name, instance, skip_notrace):
    try:
        LOG.info("Unconfiguring %s." % (component_name))
        instance.unconfigure()
        LOG.info("Pre-uninstall %s." % (component_name))
        instance.pre_uninstall()
        LOG.info("Uninstalling %s." % (component_name))
        instance.uninstall()
        LOG.info("Post-uninstall %s." % (component_name))
        instance.post_uninstall()
    except excp.NoTraceException, e:
        if skip_notrace:
            LOG.info("Passing on uninstalling %s since no trace file was found." % (component_name))
        else:
            raise


def _run_components(action_name, component_order, components, distro, root_dir, program_args):
    LOG.info("Will %s [%s] (in that order) using root directory \"%s\"" % (action_name, ", ".join(component_order), root_dir))
    non_components = set(components.keys()).difference(set(component_order))
    if non_components:
        LOG.info("Using reference components [%s]" % (", ".join(sorted(non_components))))
    pkg_manager = _get_pkg_manager(distro, program_args.pop('keep_packages', True))
    config = common.get_config()
    #form the active instances (this includes ones we won't use)
    all_instances = {}
    stop_instances = {}
    for component in components.keys():
        action_cls = common.get_action_cls(action_name, component)
        instance = action_cls(instances=all_instances,
                            distro=distro,
                            packager=pkg_manager,
                            config=config,
                            root=root_dir,
                            opts=components.get(component, list()))
        all_instances[component] = instance
    #run anything before it gets going...
    _pre_run(action_name, root_dir=root_dir, pkg=pkg_manager, cfg=config)
    results = list()
    for component in component_order:
        #this instance was just made
        instance = all_instances.get(component)
        #activate the correct function for the given action
        if action_name == settings.INSTALL:
            install_result = _install(component, instance)
            if install_result:
                if type(install_result) == list:
                    results += install_result
                else:
                    results.append(str(install_result))
        elif action_name == settings.STOP:
            _stop(component, instance, program_args.get('force', False))
        elif action_name == settings.START:
            start_result = _start(component, instance)
            if start_result:
                if type(start_result) == list:
                    results += start_result
                else:
                    results.append(str(start_result))
        elif action_name == settings.UNINSTALL:
            if component not in _NO_AUTO_STOP:
                # always stop first. doesn't hurt if already stopped - but makes
                # sure that there are no lingering processes if not
                try:
                    stop_cls = common.get_action_cls(settings.STOP, component)
                    stop_instance = stop_cls(instances=stop_instances,
                                               distro=distro,
                                               packager=pkg_manager,
                                               config=config,
                                               root=root_dir,
                                               opts=components.get(component, list()))
                    _stop(component, stop_instance, program_args.get('force', False))
                except excp.StopException:
                    LOG.warn("Failed at stopping %s before uninstalling, skipping stop.", component)
            _uninstall(component, instance, program_args.get('force', False))
    #display any configs touched...
    _print_cfgs(config, action_name)
    #any post run actions go now
    _post_run(action_name, root_dir=root_dir, pkg=pkg_manager, cfg=config)
    return results


def _run_action(args):
    defaulted_components = False
    components = utils.parse_components(args.pop("components"))
    if not components:
        defaulted_components = True
        components = common.get_default_components()
    action = _clean_action(args.pop("action"))
    if not action:
        print(utils.color_text("No valid action specified!", "red"))
        return False
    rootdir = args.pop("dir")
    if rootdir is None:
        print(utils.color_text("No root directory specified!", "red"))
        return False
    #ensure os/distro is known
    (distro, platform) = utils.determine_distro()
    if distro is None:
        print("Unsupported platform " + utils.color_text(platform, "red") + "!")
        return False
    #start it
    (rep, maxlen) = utils.welcome(_WELCOME_MAP.get(action))
    header = utils.center_text("Action Runner", rep, maxlen)
    print(header)
    if not defaulted_components:
        LOG.info("Activating components [%s]" % (", ".join(sorted(components.keys()))))
    else:
        LOG.info("Activating default components [%s]" % (", ".join(sorted(components.keys()))))
    #need to figure out dependencies for components (if any)
    ignore_deps = args.pop('ignore_deps', False)
    component_order = None
    if not ignore_deps:
        all_components_deps = common.get_components_deps(action, components)
        component_diff = set(all_components_deps.keys()).difference(components.keys())
        if component_diff:
            LOG.info("Having to activate dependent components: [%s]" % (", ".join(sorted(component_diff))))
            for new_component in component_diff:
                components[new_component] = list()
        component_order = utils.get_components_order(all_components_deps)
    else:
        component_order = components.keys()
    #see if we have previously already done the components
    component_skips = _check_roots(action, rootdir, component_order)
    for c in component_skips:
        components.pop(c)
        component_order.remove(c)
    #reverse them so that we stop in the reverse order
    #and that we uninstall in the reverse order which seems to make sense
    if action in _REVERSE_ACTIONS:
        component_order.reverse()
    #add in any that will just be referenced but which will not actually do anything (ie the action will not be applied to these)
    ref_components = utils.parse_components(args.pop("ref_components"))
    for c in ref_components.keys():
        if c not in components:
            components[c] = ref_components.get(c)
    #now do it!
    LOG.info("Starting action [%s] on %s for distro [%s]" % (action, date.rcf8222date(), distro))
    results = _run_components(action, component_order, components, distro, rootdir, args)
    LOG.info("Finished action [%s] on %s" % (action, date.rcf8222date()))
    if results:
        LOG.info('Check [%s] for traces of what happened.' % ", ".join(results))
    return True


def run(args):
    return _run_action(args)
