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
from anvil import utils

from anvil.helpers import glance


def get_config():

    config = cfg.ProxyConfig()
    config.add_read_resolver(cfg.EnvResolver())
    config.add_read_resolver(cfg.ConfigResolver(cfg.IgnoreMissingConfigParser(fns=cfg_helpers.find_config())))

    config.add_password_resolver(passwords.ConfigPassword(config))
    config.add_password_resolver(passwords.InputPassword(config))
    config.add_password_resolver(passwords.RandomPassword(config))

    return config


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
    utils.welcome(prog_name="Image uploader tool")
    cfg = get_config()
    glance.UploadService(cfg).install(uris)
