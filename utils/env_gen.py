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

import logging
import logging.config
import optparse
import os
import sys

POSSIBLE_TOPDIR = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))
sys.path.insert(0, POSSIBLE_TOPDIR)

log_fn = os.getenv('LOG_FILE')
if(log_fn == None):
    log_fn = os.path.normpath(os.path.join("conf", 'logging.ini'))
logging.config.fileConfig(log_fn)

from devstack import cfg
from devstack import utils
from devstack.progs import common


PROG_NAME = "Env. file generator"

CFG_MAKE = {
    'ADMIN_PASSWORD': ('passwords', 'horizon_keystone_admin'),
    'MYSQL_PASSWORD': ('passwords', 'sql'),
    'RABBIT_PASSWORD': ('passwords', 'rabbit'),
    'SERVICE_TOKEN': ('passwords', 'service_token'),
    'FLAT_INTERFACE': ('nova', 'flat_interface'),
}

DEF_FN = 'localrc'


def write_line(text, fh):
    fh.write(text)
    fh.write(os.linesep)


def format_env(name, value):
    return "%s=%s" % (name, value)


def main():
    opts = optparse.OptionParser()
    opts.add_option("-o", "--output", dest="filename",
         help="write output to FILE", metavar="FILE")
    (options, args) = opts.parse_args()
    fn = options.filename
    if not fn:
        fn = DEF_FN
    utils.welcome(PROG_NAME)
    cfg = common.get_config()
    with open(fn, "w") as fh:
        for (out_name, cfg_data) in CFG_MAKE.items():
            section = cfg_data[0]
            key = cfg_data[1]
            value = cfg.get(section, key)
            write_line(format_env(out_name, value), fh)
    print("Check file \"%s\" for your environment configuration." % (os.path.normpath(fn)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
