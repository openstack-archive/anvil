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

from anvil.helpers import glance as ghelper
from anvil.helpers import keystone as khelper


def get_config():

    config = cfg.ProxyConfig()
    config.add_read_resolver(cfg.EnvResolver())
    config_fns = cfg_helpers.get_config_locations([os.path.join(possible_topdir, 'conf', 'anvil.ini')])
    real_fns = cfg_helpers.find_config(config_fns)
    config.add_read_resolver(cfg.ConfigResolver(cfg.RewritableConfigParser(fns=real_fns)))

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
    cleaned_uris = [x.strip() for x in uris if len(x.strip())]
    if not cleaned_uris:
        parser.error("No uris provided, sorry not gonna do it!")

    setup_logging(len(options.verbosity))
    utils.welcome(prog_name="Image uploader tool")
    cfg = get_config()
    params = {}
    params['glance'] = ghelper.get_shared_params(cfg)
    params['keystone'] = khelper.get_shared_params(cfg)
    ghelper.UploadService(params).install(uris)
