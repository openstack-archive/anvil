#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

sys.path.insert(0, os.path.join(os.path.abspath(os.pardir)))
sys.path.insert(0, os.path.abspath(os.getcwd()))

from anvil import actions
from anvil import colorizer
from anvil import distro
from anvil import env
from anvil import exceptions as excp
from anvil import log as logging
from anvil import opts
from anvil import persona
from anvil import settings
from anvil import shell as sh
from anvil import utils

from anvil.pprint import center_text


LOG = logging.getLogger()
ANVIL_DIR = "/etc/anvil/"
SETTINGS_FN = "/etc/anvil/settings.yaml"


def run(args):
    """
    Starts the execution after args have been parsed and logging has been setup.

    Arguments: N/A
    Returns: True for success to run, False for failure to start
    """
    LOG.debug("CLI arguments are:")
    utils.log_object(args, logger=LOG, level=logging.DEBUG, item_max_len=128)

    # Keep the old args around so we have the full set to write out
    saved_args = dict(args)
    action = args.pop("action", '').strip().lower()
    if action not in actions.names():
        raise excp.OptionException("Invalid action name %r specified!" % (action))

    # Determine + setup the root directory...
    # If not provided attempt to locate it via the environment control files
    args_root_dir = args.pop("dir")
    root_dir = env.get_key('INSTALL_ROOT')
    if not root_dir:
        root_dir = args_root_dir
    if not root_dir:
        root_dir = sh.joinpths(sh.gethomedir(), 'openstack')
    root_dir = sh.abspth(root_dir)
    sh.mkdir(root_dir)

    persona_fn = args.pop('persona_fn')
    if not persona_fn:
        raise excp.OptionException("No persona file name specified!")
    if not sh.isfile(persona_fn):
        raise excp.OptionException("Invalid persona file %r specified!" % (persona_fn))

    # !!
    # Here on out we should be using the logger (and not print)!!
    # !!

    # Stash the dryrun value (if any)
    if 'dryrun' in args:
        env.set("ANVIL_DRYRUN", str(args['dryrun']))

    # Ensure the anvil etc dir is there if others are about to use it
    ensure_anvil_dir()

    # Load the distro
    dist = distro.load(settings.DISTRO_DIR)
    
    # Load + verify the person
    try:
        persona_obj = persona.load(persona_fn)
        persona_obj.verify(dist)
    except Exception as e:
        raise excp.OptionException("Error loading persona file: %s due to %s" % (persona_fn, e))

    # Get the object we will be running with...
    runner_cls = actions.class_for(action)
    runner = runner_cls(distro=dist,
                        root_dir=root_dir,
                        name=action,
                        cli_opts=args)

    (repeat_string, line_max_len) = utils.welcome()
    print(center_text("Action Runner", repeat_string, line_max_len))

    # Now that the settings are known to work, store them for next run
    store_current_settings(saved_args)

    LOG.info("Starting action %s on %s for distro: %s",
             colorizer.quote(action), colorizer.quote(utils.iso8601()),
             colorizer.quote(dist.name))
    LOG.info("Using persona: %s", colorizer.quote(persona_fn))
    LOG.info("In root directory: %s", colorizer.quote(root_dir))

    start_time = time.time()
    runner.run(persona_obj)
    end_time = time.time()

    pretty_time = utils.format_time(end_time - start_time)
    LOG.info("It took %s seconds or %s minutes to complete action %s.",
             colorizer.quote(pretty_time['seconds']), colorizer.quote(pretty_time['minutes']), colorizer.quote(action))


def load_previous_settings():
    settings_prev = None
    try:
        # Don't use sh here so that we always
        # read this (even if dry-run)    
        with open(SETTINGS_FN, 'r') as fh:
            settings_prev = utils.load_yaml_text(fh.read())
    except Exception:
        # Errors could be expected on format problems
        # or on the file not being readable....
        pass
    return settings_prev


def ensure_anvil_dir():
    if not sh.isdir(ANVIL_DIR):
        with sh.Rooted(True):
            os.makedirs(ANVIL_DIR)
            (uid, gid) = sh.get_suids()
            sh.chown_r(ANVIL_DIR, uid, gid)


def store_current_settings(settings):
    try:
        # Remove certain keys that just shouldn't be saved
        to_save = dict(settings)
        for k in ['action', 'verbose', 'dryrun']:
            if k in settings:
                to_save.pop(k, None)
        with sh.Rooted(True):
            with open(SETTINGS_FN, 'w') as fh:
                fh.write("# Anvil last used settings\n")
                fh.write(utils.add_header(SETTINGS_FN, utils.prettify_yaml(to_save)))
                fh.flush()
        (uid, gid) = sh.get_suids()
        sh.chown(SETTINGS_FN, uid, gid)
    except Exception as e:
        LOG.debug("Failed writing to %s due to %s", SETTINGS_FN, e)


def main():
    """
    Starts the execution of without
    injecting variables into the global namespace. Ensures that
    logging is setup and that sudo access is available and in-use.

    Arguments: N/A
    Returns: 1 for success, 0 for failure
    """
    
    # Do this first so people can see the help message...
    args = opts.parse(load_previous_settings())

    # Configure logging levels
    log_level = logging.INFO
    if args['verbose'] or args['dryrun']:
        log_level = logging.DEBUG
    logging.setupLogging(log_level)

    LOG.debug("Log level is: %s" % (logging.getLevelName(log_level)))

    def clean_exc(exc):
        msg = str(exc).strip()
        if msg.endswith(".") or msg.endswith("!"):
            return msg
        else:
            return msg + "."

    def traceback_fn():
        traceback = None
        if log_level < logging.INFO:
            # See: http://docs.python.org/library/traceback.html
            # When its not none u get more detailed info about the exception
            traceback = sys.exc_traceback
        tb.print_exception(sys.exc_type, sys.exc_value,
                traceback, file=sys.stdout)

    try:
        # Drop to usermode
        sh.user_mode(quiet=False)
    except excp.AnvilException as e:
        print(clean_exc(e))
        print("This program should be running via %s, is it not?" % (colorizer.quote('sudo', quote_color='red')))
        return 1

    try:
        run(args)
        utils.goodbye(True)
        return 0
    except excp.OptionException as e:
        print(clean_exc(e))
        print("Perhaps you should try %s" % (colorizer.quote('--help', quote_color='red')))
        return 1
    except Exception:
        utils.goodbye(False)
        traceback_fn()
        return 1


if __name__ == "__main__":
    rc = main()
    # Switch back to root mode for anything
    # that needs to run in that mode for cleanups and etc...
    try:
        sh.root_mode(quiet=False)
    except excp.AnvilException:
        pass
    sys.exit(rc)
