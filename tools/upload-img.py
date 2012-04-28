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

from devstack.components import keystone
from devstack.components import glance
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


def get_config():
    base_config = cfg.IgnoreMissingConfigParser()
    stack_config = find_config()
    if stack_config:
        base_config.read([stack_config])
    config = cfg.ProxyConfig()
    config.add_read_resolver(cfg.EnvResolver())
    config.add_read_resolver(cfg.ConfigResolver(base_config))
    pw_gen = passwords.PasswordGenerator(config)
    upload_cfg = dict()
    upload_cfg.update(glance.get_shared_params(config))
    upload_cfg.update(keystone.get_shared_params(config, pw_gen))
    return upload_cfg


def setup_logging(level):
    if level == 1:
        logging.setupLogging(logging.INFO)
    else:
        logging.setupLogging(logging.DEBUG)


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-u", "--uri",
        action="append",
        dest="uris",
        metavar="URI",
        help=("uri to attempt to upload to glance"))
    parser.add_option("-v", "--verbose",
        action="append_const",
        const=1,
        dest="verbosity",
        default=[1],
        help="increase the verbose level")
    (options, args) = parser.parse_args()
    uris = options.uris or list()
    cleaned_uris = list()
    for uri in uris:
        uri = uri.strip()
        if uri:
            cleaned_uris.append(uri)

    setup_logging(len(options.verbosity))
    uploader.Service(get_config()).install(uris)
