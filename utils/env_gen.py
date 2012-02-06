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
import subprocess
import sys

POSSIBLE_TOPDIR = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))
sys.path.insert(0, POSSIBLE_TOPDIR)

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
    'HOST_IP': ('host', 'ip'),
}

DEF_FN = 'localrc'

#various settings we will output
EC2_PORT = 8773
S3_PORT = 3333

#these are pretty useless
EC2_USER_ID = 42
EC2_ACCESS_KEY = 'demo'

#change if you adjust keystone
NOVA_PORT = 5000
NOVA_VERSION = '1.1'
NOVA_PROJECT = 'demo'
NOVA_REGION = 'RegionOne'

#change if you adjust keystone
OS_TENANT_NAME = 'demo'
OS_USERNAME = 'demo'
OS_AUTH_PORT = 5000


def write_env(name, value, fh):
    str_value = str(value)
    escaped_val = subprocess.list2cmdline([str_value])
    if str_value != escaped_val:
        fh.write("export %s=\"%s\"" % (name, escaped_val))
    else:
        fh.write("export %s=%s" % (name, str_value))
    fh.write(os.linesep)


def generate_ec2_env(fh, cfg):
    fh.write(os.linesep)
    fh.write('# EC2 and/or S3 stuff')
    fh.write(os.linesep)
    ip = cfg.get('host', 'ip')
    write_env('EC2_URL', 'http://%s:%s/services/Cloud' % (ip, EC2_PORT), fh)
    write_env('S3_URL', 'http://%s:%s/services/Cloud' % (ip, S3_PORT), fh)
    write_env('EC2_ACCESS_KEY', EC2_ACCESS_KEY, fh)
    write_env('EC2_SECRET_KEY', cfg.get('passwords', 'horizon_keystone_admin'), fh)
    write_env('EC2_USER_ID', EC2_USER_ID, fh)
    write_env('EC2_CERT', '~/cert.pem', fh)


def generate_nova_env(fh, cfg):
    fh.write(os.linesep)
    fh.write('# Nova stuff')
    fh.write(os.linesep)
    ip = cfg.get('host', 'ip')
    write_env('NOVA_PASSWORD', cfg.get('passwords', 'horizon_keystone_admin'), fh)
    write_env('NOVA_URL', 'http://%s:%s/v2.0' % (ip, NOVA_PORT), fh)
    write_env('NOVA_PROJECT_ID', NOVA_PROJECT, fh)
    write_env('NOVA_REGION_NAME', NOVA_REGION, fh)
    write_env('NOVA_VERSION', NOVA_VERSION, fh)
    write_env('NOVA_CERT', '~/cacert.pem', fh)


def generate_os_env(fh, cfg):
    fh.write(os.linesep)
    fh.write('# Openstack stuff')
    fh.write(os.linesep)
    ip = cfg.get('host', 'ip')
    write_env('OS_PASSWORD', cfg.get('passwords', 'horizon_keystone_admin'), fh)
    write_env('OS_TENANT_NAME', OS_TENANT_NAME, fh)
    write_env('OS_USERNAME', OS_USERNAME, fh)
    write_env('OS_AUTH_URL', 'http://%s:%s/v2.0' % (ip, OS_AUTH_PORT), fh)


def generate_local_rc(fn=None, cfg=None):
    if not fn:
        fn = DEF_FN
    if not cfg:
        cfg = common.get_config()
    with open(fn, "w") as fh:
        fh.write('# General stuff')
        fh.write(os.linesep)
        for (out_name, cfg_data) in CFG_MAKE.items():
            section = cfg_data[0]
            key = cfg_data[1]
            value = cfg.get(section, key)
            write_env(out_name, value, fh)
        generate_ec2_env(fh, cfg)
        generate_nova_env(fh, cfg)
        generate_os_env(fh, cfg)


def main():
    opts = optparse.OptionParser()
    opts.add_option("-o", "--output", dest="filename",
         help="write output to FILE", metavar="FILE")
    (options, args) = opts.parse_args()
    utils.welcome(PROG_NAME)
    fn = options.filename
    if not fn:
        fn = DEF_FN
    generate_local_rc(fn)
    print("Check file \"%s\" for your environment configuration." \
              % (os.path.normpath(fn)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
