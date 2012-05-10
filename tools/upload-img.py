#!/usr/bin/env python

import os
import sys
from optparse import OptionParser

possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))
if os.path.exists(os.path.join(possible_topdir,
                               'anvil',
                               '__init__.py')):
    sys.path.insert(0, possible_topdir)


from anvil import cfg
from anvil import cfg_helpers
from anvil import log as logging
from anvil import passwords
from anvil import settings
from anvil import shell as sh
from anvil import utils

from anvil.components import keystone
from anvil.components import glance

from anvil.helpers import uploader


class CfgProxy:
    def __init__(self, cfg, pw_gen):
        self.cfg = cfg
        self.pw_gen = pw_gen


def get_config():
    base_config = cfg.IgnoreMissingConfigParser()
    config_location = cfg_helpers.find_config()
    if config_location:
        base_config.read([config_location])
    config = cfg.ProxyConfig()
    config.add_read_resolver(cfg.EnvResolver())
    config.add_read_resolver(cfg.ConfigResolver(base_config))
    pw_gen = passwords.PasswordGenerator(config)
    return CfgProxy(config, pw_gen)


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

    cfg = get_config()
    uploader.Service(cfg).install(uris)
