#!/usr/bin/env python

import os
import sys
from optparse import OptionParser

possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))
if os.path.exists(os.path.join(possible_topdir,
                               'devstack',
                               '__init__.py')):
    sys.path.insert(0, possible_topdir)


from devstack import cfg
from devstack import log as logging
from devstack import passwords
from devstack import settings
from devstack import shell as sh
from devstack import utils

from devstack.image import uploader


def find_config():
    """
    Finds the stack configuration file.

    Arguments:
        args: command line args
    Returns: the file location or None if not found
    """

    locs = []
    locs.append(settings.STACK_CONFIG_LOCATION)
    locs.append(sh.joinpths("/etc", "devstack", "stack.ini"))
    locs.append(sh.joinpths(settings.STACK_CONFIG_DIR, "stack.ini"))
    locs.append(sh.joinpths("conf", "stack.ini"))
    for path in locs:
        if sh.isfile(path):
            return path
    return None


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-u", "--uri",
        action="append",
        dest="uris",
        metavar="URI",
        help=("uri to attempt to upload to glance"))
    (options, args) = parser.parse_args()
    uris = options.uris or list()
    uri_sep = ",".join(uris)
    logging.setupLogging(logging.INFO)
    base_config = cfg.IgnoreMissingConfigParser()
    stack_config = find_config()
    if stack_config:
        base_config.read([stack_config])
    base_config.set('img', 'image_urls', uri_sep)
    config = cfg.ProxyConfig()
    config.add_read_resolver(cfg.EnvResolver(base_config))
    pw_gen = passwords.PasswordGenerator(config)
    uploader = uploader.Service(config, pw_gen)
    uploader.install()
