#!/usr/bin/env python

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
#    under the License.

import os
import sys
import time
import traceback as tb

from anvil import actions
from anvil import cfg
from anvil import cfg_helpers
from anvil import colorizer
from anvil import date
from anvil import distro
from anvil import env
from anvil import env_rc
from anvil import log as logging
from anvil import opts
from anvil import passwords
from anvil import persona
from anvil import settings
from anvil import shell as sh
from anvil import utils


LOG = logging.getLogger()

# Which rc files we will attempt to load
RC_FILES = [
    sh.abspth(settings.gen_rc_filename('core')),
]


def load_rc_files():
    """
    Loads the desired set of rc files that smithy will use to
    pre-populate its environment settings from.

    Arguments: N/A
    Returns: the number of files loaded
    """

    loaded_am = 0
    for fn in RC_FILES:
        try:
            LOG.info("Attempting to load file %s which has your environment settings.", colorizer.quote(fn))
            am_loaded = env_rc.RcReader().load(fn)
            LOG.info("Loaded %s settings.", colorizer.quote(am_loaded))
            loaded_am += 1
        except IOError:
            LOG.warn('Error reading file located at %s. Skipping loading it.', colorizer.quote(fn))
    return loaded_am


def load_verify_persona(fn, distro_instance):
    """
    Loads and verifies the given persona under the given distro.

    Arguments:
        fn: persona file name/path
        distro_instance: the distrobution object to use for verification
    Returns: the persona instance from that file (verified)
    """

    instance = persona.Persona.load_file(fn)
    instance.verify(distro_instance)
    return instance


def setup_root(root_dir):
    """
    Ensures the root dir is created and setup as desired.

    Arguments:
        root_dir: the location of the desired root install directory
    Returns: N/A
    """

    if not sh.isdir(root_dir):
        sh.mkdir(root_dir)


def establish_config(args):
    """
    Creates the stack configuration object using the set of
    desired configuration resolvers+password resolvers to be used and returns
    the wrapper that knows how to activate those resolvers.

    Arguments:
        args: command line args
    """

    config = cfg.ProxyConfig()
    config.add_read_resolver(cfg.CliResolver.create(args['cli_overrides']))
    config.add_read_resolver(cfg.EnvResolver())
    start_configs = []
    if args['config_fn']:
        start_configs.append(args['config_fn'])
    else:
        start_configs.extend(cfg_helpers.get_config_locations())
    real_configs = cfg_helpers.find_config(start_configs)
    config.add_read_resolver(cfg.ConfigResolver(cfg.RewritableConfigParser(fns=real_configs)))
    utils.log_iterable(utils.get_class_names(config.read_resolvers),
        header="Config lookup will use the following resolvers:",
        logger=LOG)

    config.add_password_resolver(passwords.ConfigPassword(config))
    if args.get('prompt_for_passwords', True):
        config.add_password_resolver(passwords.InputPassword(config))
    config.add_password_resolver(passwords.RandomPassword(config))
    utils.log_iterable(utils.get_class_names(config.pw_resolvers),
        header="Password finding will use the following lookups:",
        logger=LOG)

    return config


def backup_persona(install_dir, action, persona_fn):
    (name, ext) = os.path.splitext(os.path.basename(persona_fn))
    ext = ext.lstrip(".")
    if ext:
        new_name = "%s.%s.%s" % (name, action, ext)
    else:
        new_name = "%s.%s" % (name, action)
    new_path = sh.joinpths(install_dir, new_name)
    sh.copy(persona_fn, new_path)
    return new_path


def run(args):
    """
    Starts the execution after args have been parsed and logging has been setup.

    Arguments: N/A
    Returns: True for success to run, False for failure to start
    """

    (repeat_string, line_max_len) = utils.welcome()
    print(utils.center_text("Action Runner", repeat_string, line_max_len))

    action = args.pop("action", '').strip().lower()
    if action not in actions.get_action_names():
        print(colorizer.color("No valid action specified!", "red"))
        return False

    loaded_rcs = False
    root_dir = args.pop("dir")
    if not root_dir:
        load_rc_files()
        loaded_rcs = True
        root_dir = env.get_key(env_rc.INSTALL_ROOT)
        if not root_dir:
            root_dir = sh.joinpths(sh.gethomedir(), 'openstack')
    root_dir = sh.abspth(root_dir)
    setup_root(root_dir)

    persona_fn = args.pop('persona_fn')
    if not persona_fn or not sh.isfile(persona_fn):
        print(colorizer.color("No valid persona file name specified!", "red"))
        return False
    persona_fn = sh.abspth(persona_fn)

    # !!
    # Here on out we should be using the logger (and not print)!!
    # !!

    # If we didn't load them before, load them now
    if not loaded_rcs:
        load_rc_files()
        loaded_rcs = True

    # Stash the dryrun value (if any) into the global configuration
    sh.set_dryrun(args.get('dryrun', False))

    # Params for the runner...
    dist = distro.Distro.get_current()
    persona_inst = load_verify_persona(persona_fn, dist)
    config = establish_config(args)

    runner_cls = actions.get_action_class(action)
    runner = runner_cls(dist,
                            config,
                            root_dir=root_dir,
                            **args)

    LOG.info("Starting action %s on %s for distro: %s",
                colorizer.quote(action), colorizer.quote(date.rcf8222date()), colorizer.quote(dist.name))
    LOG.info("Using persona: %s", colorizer.quote(persona_fn))
    LOG.info("In root directory: %s", colorizer.quote(root_dir))
    persona_bk_fn = backup_persona(root_dir, action, persona_fn)
    if persona_bk_fn:
        LOG.info("Backed up persona %s to %s so that you can reference it later.",
                colorizer.quote(persona_fn), colorizer.quote(persona_bk_fn))

    start_time = time.time()
    runner.run(persona_inst)
    end_time = time.time()

    pretty_time = utils.format_time(end_time - start_time)
    LOG.info("It took %s seconds or %s minutes to complete action %s.",
        colorizer.quote(pretty_time['seconds']), colorizer.quote(pretty_time['minutes']), colorizer.quote(action))

    LOG.info("After action %s your settings which were read/set are:", colorizer.quote(action))
    cfg_groups = dict()
    read_set_keys = (config.opts_read.keys() + config.opts_set.keys())
    for c in read_set_keys:
        cfg_id = cfg_helpers.make_id(c, None)
        cfg_groups[cfg_id] = colorizer.quote(c.capitalize(), underline=True)

    # Now print and order/group by our selection here
    cfg_ordering = sorted(cfg_groups.keys())
    cfg_helpers.pprint(config.opts_cache, cfg_groups, cfg_ordering)

    return True


def construct_log_level(verbosity_level, dry_run=False):
    log_level = logging.INFO
    if verbosity_level >= 3:
        log_level = logging.DEBUG
    elif verbosity_level == 2 or dry_run:
        log_level = logging.AUDIT
    return log_level


def main():
    """
    Starts the execution of without
    injecting variables into the global namespace. Ensures that
    logging is setup and that sudo access is available and in-use.

    Arguments: N/A
    Returns: 1 for success, 0 for failure
    """

    # Do this first so people can see the help message...
    args = opts.parse()
    prog_name = sys.argv[0]

    # Configure logging
    log_level = construct_log_level(args['verbosity'], args['dryrun'])
    logging.setupLogging(log_level)

    LOG.debug("Command line options %s" % (args))
    LOG.debug("Log level is: %s" % (log_level))

    # Will need root to setup openstack
    if not sh.got_root():
        rest_args = sys.argv[1:]
        print("This program requires a user with sudo access.")
        msg = "Perhaps you should try %s %s" % \
                (colorizer.color("sudo %s" % (prog_name), "red", True), " ".join(rest_args))
        print(msg)
        return 1

    try:
        # Drop to usermode
        sh.user_mode(quiet=False)
        started_ok = run(args)
        if not started_ok:
            me = colorizer.color(prog_name, "red", True)
            me += " " + colorizer.color('--help', 'red')
            print("Perhaps you should try %s" % (me))
            return 1
        else:
            utils.goodbye(True)
            return 0
    except Exception:
        utils.goodbye(False)
        traceback = None
        if log_level < logging.INFO:
            # See: http://docs.python.org/library/traceback.html
            # When its not none u get more detailed info about the exception
            traceback = sys.exc_traceback
        tb.print_exception(sys.exc_type, sys.exc_value,
                traceback, file=sys.stdout)
        return 1


if __name__ == "__main__":
    sys.exit(main())
