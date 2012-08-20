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
import platform

# These are safe to import without bringing in non-core
# python dependencies...
from anvil import bootstrap
from anvil import env


def what_ran():
    prog_name = sys.argv[0]
    rest_args = sys.argv[1:]
    return (prog_name, " ".join(rest_args))


# Check if supported
if (not bootstrap.is_supported() and 
    not str(env.get_key('FORCE')).lower().strip() in ['yes', 'on', '1', 'true']):
    sys.stderr.write("WARNING: this script has not been tested on distribution: %s\n" % (platform.platform()))
    sys.stderr.write("If you wish to run this script anyway run with FORCE=yes\n")
    sys.exit(1)

# Bootstrap anvil, call before importing anything else from anvil
if bootstrap.strap():
    sys.stderr.write("Please re-run %r so that changes are reflected.\n" % (" ".join(what_ran())))
    sys.exit(0)

from anvil import actions
from anvil import cfg
from anvil import colorizer
from anvil import distro
from anvil import log as logging
from anvil import opts
from anvil import passwords
from anvil import persona
from anvil import settings
from anvil import shell as sh
from anvil import utils

from anvil.pprint import center_text

from ordereddict import OrderedDict


LOG = logging.getLogger()


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
    print(center_text("Action Runner", repeat_string, line_max_len))

    action = args.pop("action", '').strip().lower()
    if action not in actions.names():
        raise RuntimeError("Invalid action name %r specified!" % (action))

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
        raise RuntimeError("No persona file name specified!")
    if not sh.isfile(persona_fn):
        raise RuntimeError("Invalid persona file %r specified!" % (persona_fn))

    # !!
    # Here on out we should be using the logger (and not print)!!
    # !!

    # Stash the dryrun value (if any)
    if 'dryrun' in args:
        env.set("ANVIL_DRYRUN", str(args['dryrun']))

    # Load the distro
    dist = distro.load(settings.DISTRO_DIR)
    
    # Load + verify the person
    try:
        persona_obj = persona.load(persona_fn)
        persona_obj.verify(dist)
    except Exception as e:
        raise RuntimeError("Error loading persona file: %s due to %s" % (person_fn, e))

    # Get the object we will be running with...
    runner_cls = actions.class_for(action)
    runner = runner_cls(distro=dist,
                        root_dir=root_dir,
                        name=action,
                        **args)

    LOG.info("Starting action %s on %s for distro: %s",
             colorizer.quote(action), colorizer.quote(utils.rcf8222date()),
             colorizer.quote(dist.name))
    LOG.info("Using persona: %s", colorizer.quote(persona_fn))
    LOG.info("In root directory: %s", colorizer.quote(root_dir))
    LOG.debug("Using environment settings:")
    utils.log_object(env.get(), logger=LOG, level=logging.DEBUG, item_max_len=64)
    persona_bk_fn = backup_persona(root_dir, action, persona_fn)
    if persona_bk_fn:
        LOG.info("Backed up persona %s to %s so that you can reference it later.",
                 colorizer.quote(persona_fn), colorizer.quote(persona_bk_fn))

    start_time = time.time()
    runner.run(persona_obj)
    end_time = time.time()

    pretty_time = utils.format_time(end_time - start_time)
    LOG.info("It took %s seconds or %s minutes to complete action %s.",
             colorizer.quote(pretty_time['seconds']), colorizer.quote(pretty_time['minutes']), colorizer.quote(action))

    LOG.debug("Final environment settings:")
    utils.log_object(env.get(), logger=LOG, level=logging.DEBUG, item_max_len=64)


def main():
    """
    Starts the execution of without
    injecting variables into the global namespace. Ensures that
    logging is setup and that sudo access is available and in-use.

    Arguments: N/A
    Returns: 1 for success, 0 for failure
    """
    (prog_name, rest_args) = what_ran()
    
    # Do this first so people can see the help message...
    args = opts.parse()

    # Configure logging levels
    log_level = logging.INFO
    if args['verbosity'] >= 2 or args['dryrun']:
        log_level = logging.DEBUG
    logging.setupLogging(log_level)

    LOG.debug("Command line options:")
    utils.log_object(args, item_max_len=64, logger=LOG, level=logging.DEBUG)
    LOG.debug("Log level is: %s" % (logging.getLevelName(log_level)))

    # Will need root to setup openstack
    if not sh.got_root():
        print("This program requires a user with sudo access.")
        print("Perhaps you should try %s %s" % 
              (colorizer.color("sudo %s" % (prog_name), "red", True), " ".join(rest_args)))
        return 1

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
        run(args)
        utils.goodbye(True)
        return 0
    except Exception:
        utils.goodbye(False)
        traceback_fn()
        return 1


if __name__ == "__main__":
    sys.exit(main())
