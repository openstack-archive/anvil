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

from urlparse import urlunparse
import os
import re
import subprocess

from devstack import date
from devstack import env

#general extraction cfg keys
CFG_MAKE = {
    'ADMIN_PASSWORD': ('passwords', 'horizon_keystone_admin'),
    'MYSQL_PASSWORD': ('passwords', 'sql'),
    'RABBIT_PASSWORD': ('passwords', 'rabbit'),
    'SERVICE_TOKEN': ('passwords', 'service_token'),
    'FLAT_INTERFACE': ('nova', 'flat_interface'),
    'HOST_IP': ('host', 'ip'),
}

#default ports
EC2_PORT = 8773
S3_PORT = 3333
NOVA_PORT = 5000
OS_AUTH_PORT = 5000

#how we know if a line is an export or if it isn't (simpe edition)
EXP_PAT = re.compile("^\s*export\s+(.*?)=(.*?)$", re.IGNORECASE)

#how we unquote a string (simple edition)
QUOTED_PAT = re.compile(r"^\s*[\"](.*)[\"]\s*$")


def _write_line(text, fh):
    fh.write(text)
    fh.write(os.linesep)


def _write_env(name, value, fh):
    if value is None:
        return
    str_value = str(value)
    escaped_val = subprocess.list2cmdline([str_value])
    if str_value != escaped_val:
        _write_line("export %s=\"%s\"" % (name, escaped_val), fh)
    else:
        _write_line("export %s=%s" % (name, str_value), fh)


def _generate_ec2_env(fh, cfg):
    _write_line('# EC2 and/or S3 stuff', fh)
    ip = cfg.get('host', 'ip')

    ec2_url = cfg.get('extern', 'ec2_url')
    if not ec2_url:
        ec2_url = urlunparse(('http', "%s:%s" % (ip, EC2_PORT), "services/Cloud", '', '', ''))
    _write_env('EC2_URL', ec2_url, fh)

    s3_url = cfg.get('extern', 's3_url')
    if not s3_url:
        s3_url = urlunparse(('http', "%s:%s" % (ip, S3_PORT), "services/Cloud", '', '', ''))
    _write_env('S3_URL', s3_url, fh)

    ec2_acc_key = cfg.get('extern', 'ec2_access_key')
    _write_env('EC2_ACCESS_KEY', ec2_acc_key, fh)

    hkpw = cfg.get('passwords', 'horizon_keystone_admin', auto_pw=False)
    _write_env('EC2_SECRET_KEY', hkpw, fh)

    ec2_uid = cfg.get('extern', 'ec2_user_id')
    _write_env('EC2_USER_ID', ec2_uid, fh)

    ec2_cert = cfg.get('extern', 'ec2_cert_fn')
    _write_env('EC2_CERT', ec2_cert, fh)

    _write_line("", fh)


def _generate_nova_env(fh, cfg):
    _write_line('# Nova stuff', fh)
    ip = cfg.get('host', 'ip')

    hkpw = cfg.get('passwords', 'horizon_keystone_admin', auto_pw=False)
    _write_env('NOVA_PASSWORD', hkpw, fh)

    nv_url = cfg.get('extern', 'nova_url')
    if not nv_url:
        nv_url = urlunparse(('http', "%s:%s" % (ip, NOVA_PORT), "v2.0", '', '', ''))
    _write_env('NOVA_URL', nv_url, fh)

    nv_prj = cfg.get('extern', 'nova_project_id')
    _write_env('NOVA_PROJECT_ID', nv_prj, fh)

    nv_reg = cfg.get('extern', 'nova_region_name')
    _write_env('NOVA_REGION_NAME', nv_reg, fh)

    nv_ver = cfg.get('extern', 'nova_version')
    _write_env('NOVA_VERSION', nv_ver, fh)

    nv_cert = cfg.get("extern", 'nova_cert_fn')
    _write_env('NOVA_CERT', nv_cert, fh)

    _write_line("", fh)


def _generate_os_env(fh, cfg):
    _write_line('# Openstack stuff', fh)
    ip = cfg.get('host', 'ip')

    hkpw = cfg.get('passwords', 'horizon_keystone_admin', auto_pw=False)
    _write_env('OS_PASSWORD', hkpw, fh)

    os_ten = cfg.get('extern', 'os_tenant_name')
    _write_env('OS_TENANT_NAME', os_ten, fh)

    os_uname = cfg.get('extern', 'os_username')
    _write_env('OS_USERNAME', os_uname, fh)

    os_auth_uri = cfg.get('extern', 'os_auth_url')
    if not os_auth_uri:
        os_auth_uri = urlunparse(('http', "%s:%s" % (ip, OS_AUTH_PORT), "v2.0", '', '', ''))
    _write_env('OS_AUTH_URL', os_auth_uri, fh)

    _write_line("", fh)


def _generate_header(fh, cfg):
    header = '# Generated on %s' % (date.rcf8222date())
    _write_line(header, fh)
    _write_line("", fh)


def _generate_general(fh, cfg):
    _write_line('# General stuff', fh)
    for (out_name, cfg_data) in CFG_MAKE.items():
        (section, key) = cfg_data
        value = cfg.get(section, key, auto_pw=False)
        _write_env(out_name, value, fh)
    _write_line("", fh)


def generate_local_rc(fn, cfg):
    with open(fn, "w") as fh:
        _generate_header(fh, cfg)
        _generate_general(fh, cfg)
        _generate_ec2_env(fh, cfg)
        _generate_nova_env(fh, cfg)
        _generate_os_env(fh, cfg)


def load_local_rc(fn):
    am_set = 0
    with open(fn, "r") as fh:
        for line in fh:
            m = EXP_PAT.search(line)
            if m:
                key = m.group(1).strip()
                value = m.group(2).strip()
                #remove inline comment if any
                value = value.split("#")[0].strip()
                if len(key):
                    qmtch = QUOTED_PAT.match(value)
                    if qmtch:
                        value = qmtch.group(1).decode('string_escape').strip()
                    env.set(key, value)
                    am_set += 1
    return am_set
