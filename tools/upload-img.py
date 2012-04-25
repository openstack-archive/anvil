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


from devstack import log as logging
from devstack import utils
from devstack import cfg
from devstack import passwords
from devstack.image import uploader



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
    logging.setupLogging(logging.DEBUG)
    config = cfg.IgnoreMissingConfigParser()
    config.add_section('img')
    config.set('img', 'image_urls', uri_sep)
    pw_gen = passwords.PasswordGenerator(config)
    uploader = uploader.Service(config, pw_gen)
    uploader.install()
