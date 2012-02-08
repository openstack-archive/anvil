#!/usr/bin/env python

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

import optparse
import os
import sys

POSSIBLE_TOPDIR = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))
sys.path.insert(0, POSSIBLE_TOPDIR)

from devstack import env_rc
from devstack import utils
from devstack import shell as sh

PROG_NAME = "Env. rc file generator"

DEF_FN = 'openstackrc'


def main():
    opts = optparse.OptionParser()
    opts.add_option("-o", "--output", dest="filename",
         help="write output to FILE", metavar="FILE")
    (options, args) = opts.parse_args()
    utils.welcome(PROG_NAME)
    fn = options.filename
    if not fn:
        fn = DEF_FN
    env_rc.generate_local_rc(fn)
    print("Check file \"%s\" for your environment configuration." \
              % (sh.abspth(fn)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
