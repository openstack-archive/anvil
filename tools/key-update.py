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
from anvil import passwords
from anvil import utils

from anvil.helpers import keystone as khelper

import yaml


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
    parser.add_option("-f", "--file",
        action="store",
        dest="yaml_fn",
        metavar="FILE",
        help=("yaml file that contains your new roles/endpoints/services..."))
    parser.add_option("-v", "--verbose",
        action="append_const",
        const=1,
        dest="verbosity",
        default=[1],
        help="increase the verbose level")

    (options, args) = parser.parse_args()
    if not options.yaml_fn:
        parser.error("File option required")

    data = None
    with open(options.yaml_fn, "r") as fh:
        data = yaml.load(fh)

    setup_logging(len(options.verbosity))
    utils.welcome(prog_name="Keystone updater/init tool")
    params = khelper.get_shared_params(get_config())
    khelper.Initializer(params).initialize(**data)
