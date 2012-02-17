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
import re

from devstack import date
from devstack import env
from devstack import settings
from devstack import shell as sh
from devstack import utils

from devstack.components import keystone

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

#how we know if a line is an export or if it isn't (simpe edition)
EXP_PAT = re.compile("^\s*export\s+(.*?)=(.*?)$", re.IGNORECASE)

#how we unquote a string (simple edition)
QUOTED_PAT = re.compile(r"^\s*[\"](.*)[\"]\s*$")


class RcGenerator(object):
    def __init__(self, cfg):
        self.cfg = cfg

    def _generate_header(self):
        lines = list()
        lines.append('# Generated on %s' % (date.rcf8222date()))
        lines.append("")
        return lines

    def _make_export(self, export_name, value):
        escaped_val = sh.shellquote(value)
        full_line = "export %s=%s" % (export_name, escaped_val)
        return [full_line]

    def _make_export_cfg(self, export_name, cfg_section_key, default_val=''):
        (section, key) = cfg_section_key
        value = self.cfg.getdefaulted(section, key, default_val, auto_pw=False)
        return self._make_export(export_name, value)

    def _generate_ec2_env(self):
        lines = list()
        lines.append('# EC2 and/or S3 stuff')
        ip = self.cfg.get('host', 'ip')
        lines.extend(self._make_export_cfg('EC2_URL',
                                ('extern', 'ec2_url'),
                                urlunparse(('http', "%s:%s" % (ip, EC2_PORT), "services/Cloud", '', '', ''))))
        lines.extend(self._make_export_cfg('S3_URL',
                                ('extern', 's3_url'),
                                urlunparse(('http', "%s:%s" % (ip, S3_PORT), "services/Cloud", '', '', ''))))
        lines.extend(self._make_export_cfg('EC2_CERT',
                                ('extern', 'ec2_cert_fn')))
        lines.extend(self._make_export_cfg('EC2_USER_ID',
                                ('extern', 'ec2_user_id')))
        lines.append("")
        return lines

    def _generate_general(self):
        lines = list()
        lines.append('# General stuff')
        for (out_name, cfg_data) in CFG_MAKE.items():
            lines.extend(self._make_export_cfg(out_name, cfg_data))
        lines.append("")
        return lines

    def _generate_lines(self):
        lines = list()
        lines.extend(self._generate_header())
        lines.extend(self._generate_general())
        lines.extend(self._generate_ec2_env())
        lines.extend(self._generate_nova_env())
        lines.extend(self._generate_os_env())
        lines.extend(self._generate_euca_env())
        lines.extend(self._generate_extern_inc())
        lines.extend(self._generate_aliases())
        return lines

    def generate(self):
        lines = self._generate_lines()
        return utils.joinlinesep(*lines)

    def _generate_os_env(self):
        lines = list()
        lines.append('# Openstack stuff')
        lines.extend(self._make_export_cfg('OS_PASSWORD',
                                ('passwords', 'horizon_keystone_admin')))
        key_users = keystone.get_shared_users(self.cfg)
        key_ends = keystone.get_shared_params(self.cfg)
        lines.extend(self._make_export('OS_TENANT_NAME', key_users['DEMO_TENANT_NAME']))
        lines.extend(self._make_export('OS_USERNAME', key_users['DEMO_USER_NAME']))
        lines.extend(self._make_export('OS_AUTH_URL', key_ends['SERVICE_ENDPOINT']))
        lines.append("")
        return lines

    def _generate_aliases(self):
        lines = list()
        lines.append('# Alias stuff')
        export_inc = """
alias ec2-bundle-image="ec2-bundle-image --cert ${EC2_CERT} --privatekey ${EC2_PRIVATE_KEY} --user ${EC2_USER_ID} --ec2cert ${NOVA_CERT}"
alias ec2-upload-bundle="ec2-upload-bundle -a ${EC2_ACCESS_KEY} -s ${EC2_SECRET_KEY} --url ${S3_URL} --ec2cert ${NOVA_CERT}"
"""
        lines.append(export_inc.strip())
        lines.append("")
        return lines

    def _generate_euca_env(self):
        lines = list()
        lines.append('# Eucalyptus stuff')
        lines.extend(self._make_export_cfg('EUCALYPTUS_CERT',
                                ('extern', 'nova_cert_fn')))
        lines.append("")
        return lines

    def _generate_nova_env(self):
        lines = list()
        lines.append('# Nova stuff')
        lines.extend(self._make_export_cfg('NOVA_PASSWORD',
                                ('passwords', 'horizon_keystone_admin')))
        key_users = keystone.get_shared_users(self.cfg)
        key_ends = keystone.get_shared_params(self.cfg)
        lines.extend(self._make_export('NOVA_URL', key_ends['SERVICE_ENDPOINT']))
        lines.extend(self._make_export('NOVA_PROJECT_ID', key_users['DEMO_TENANT_NAME']))
        lines.extend(self._make_export('NOVA_USERNAME', key_users['DEMO_USER_NAME']))
        lines.extend(self._make_export_cfg('NOVA_VERSION',
                                ('nova', 'nova_version')))
        lines.extend(self._make_export_cfg('NOVA_CERT',
                                ('extern', 'nova_cert_fn')))
        lines.append("")
        return lines

    def _generate_extern_inc(self):
        lines = list()
        lines.append('# External includes stuff')
        extern_tpl = """

# Use stored ec2 env variables
if [ -f "{ec2rc_fn}" ]; then
    source "{ec2rc_fn}"
fi

# Allow local overrides of env variables
if [ -f "{localrc_fn}" ]; then
    source "{localrc_fn}"
fi

"""
        extern_inc = extern_tpl.format(ec2rc_fn=sh.abspth(settings.EC2RC_FN),
                                   localrc_fn=sh.abspth(settings.LOCALRC_FN))
        lines.append(extern_inc.strip())
        lines.append("")
        return lines


class RcLoader(object):
    def __init__(self):
        pass

    def load(self, fn):
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
