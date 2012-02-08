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

import os
import re
import subprocess

#general extraction cfg keys
CFG_MAKE = {
    'ADMIN_PASSWORD': ('passwords', 'horizon_keystone_admin'),
    'MYSQL_PASSWORD': ('passwords', 'sql'),
    'RABBIT_PASSWORD': ('passwords', 'rabbit'),
    'SERVICE_TOKEN': ('passwords', 'service_token'),
    'FLAT_INTERFACE': ('nova', 'flat_interface'),
    'HOST_IP': ('host', 'ip'),
}

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

EXP_PAT = re.compile("^export (.*?)=(.*?)$", re.IGNORECASE)


def _write_line(text, fh):
    fh.write(text)
    fh.write(os.linesep)


def _write_env(name, value, fh):
    str_value = str(value)
    escaped_val = subprocess.list2cmdline([str_value])
    if str_value != escaped_val:
        _write_line("export %s=\"%s\"" % (name, escaped_val), fh)
    else:
        _write_line("export %s=%s" % (name, str_value), fh)


def _generate_ec2_env(fh, cfg):
    _write_line('# EC2 and/or S3 stuff', fh)
    ip = cfg.get('host', 'ip')
    _write_env('EC2_URL', 'http://%s:%s/services/Cloud' % (ip, EC2_PORT), fh)
    _write_env('S3_URL', 'http://%s:%s/services/Cloud' % (ip, S3_PORT), fh)
    _write_env('EC2_ACCESS_KEY', EC2_ACCESS_KEY, fh)
    hkpw = cfg.get('passwords', 'horizon_keystone_admin', auto_pw=False)
    if hkpw:
        _write_env('EC2_SECRET_KEY', hkpw, fh)
    _write_env('EC2_USER_ID', EC2_USER_ID, fh)
    _write_env('EC2_CERT', '~/cert.pem', fh)
    _write_line("", fh)


def _generate_nova_env(fh, cfg):
    _write_line('# Nova stuff', fh)
    ip = cfg.get('host', 'ip')
    hkpw = cfg.get('passwords', 'horizon_keystone_admin', auto_pw=False)
    if hkpw:
        _write_env('NOVA_PASSWORD', hkpw, fh)
    _write_env('NOVA_URL', 'http://%s:%s/v2.0' % (ip, NOVA_PORT), fh)
    _write_env('NOVA_PROJECT_ID', NOVA_PROJECT, fh)
    _write_env('NOVA_REGION_NAME', NOVA_REGION, fh)
    _write_env('NOVA_VERSION', NOVA_VERSION, fh)
    _write_env('NOVA_CERT', '~/cacert.pem', fh)
    _write_line("", fh)


def _generate_os_env(fh, cfg):
    _write_line('# Openstack stuff', fh)
    ip = cfg.get('host', 'ip')
    hkpw = cfg.get('passwords', 'horizon_keystone_admin', auto_pw=False)
    if hkpw:
        _write_env('OS_PASSWORD', hkpw, fh)
    _write_env('OS_TENANT_NAME', OS_TENANT_NAME, fh)
    _write_env('OS_USERNAME', OS_USERNAME, fh)
    _write_env('OS_AUTH_URL', 'http://%s:%s/v2.0' % (ip, OS_AUTH_PORT), fh)
    _write_line("", fh)


def generate_local_rc(fn, cfg):
    with open(fn, "w") as fh:
        _write_line('# General stuff', fh)
        for (out_name, cfg_data) in CFG_MAKE.items():
            section = cfg_data[0]
            key = cfg_data[1]
            value = cfg.get(section, key, auto_pw=False)
            if value:
                _write_env(out_name, value, fh)
        _write_line("", fh)
        _generate_ec2_env(fh, cfg)
        _generate_nova_env(fh, cfg)
        _generate_os_env(fh, cfg)


def load_local_rc(fn):
    am_set = 0
    with open(fn, "r") as fh:
        for line in fh:
            m = EXP_PAT.search(line)
            if m:
                var = m.group(1).strip()
                value = m.group(2).strip()
                if not var in os.environ and var and value:
                    os.environ[var] = value
                    am_set += 1
    return am_set
