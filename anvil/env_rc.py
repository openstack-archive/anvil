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

from anvil import cfg_helpers
from anvil import date
from anvil import env
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.helpers import keystone as khelper

LOG = logging.getLogger(__name__)

# General extraction cfg keys + sections
CFG_MAKE = {
    'FLAT_INTERFACE': ('nova', 'flat_interface'),
    'HOST_IP': ('host', 'ip'),
}

# PW sections
PASSWORDS_MAKES = {
    'ADMIN_PASSWORD': (cfg_helpers.PW_SECTION, 'horizon_keystone_admin'),
    'SERVICE_PASSWORD': (cfg_helpers.PW_SECTION, 'service_password'),
    'RABBIT_PASSWORD': (cfg_helpers.PW_SECTION, 'rabbit'),
    'SERVICE_TOKEN': (cfg_helpers.PW_SECTION, 'service_token'),
    'MYSQL_PASSWORD': (cfg_helpers.PW_SECTION, 'sql'),
}

# Install root output name and env variable name
INSTALL_ROOT = 'INSTALL_ROOT'

# Default ports
EC2_PORT = 8773
S3_PORT = 3333

# How we know if a line is an export or if it isn't (simple edition)
EXP_PAT = re.compile("^\s*export\s+(.*?)=(.*?)$", re.IGNORECASE)

# How we unquote a string (simple edition)
QUOTED_PAT = re.compile(r"^\s*[\"](.*)[\"]\s*$")

# Allow external includes via this template
EXTERN_TPL = """
# Allow local overrides of env variables using {fn}
if [ -f "{fn}" ]; then
    source "{fn}"
fi
"""
EXTERN_INCLUDES = ['localrc', 'eucarc']


class RcWriter(object):
    def __init__(self, cfg, root_dir):
        self.cfg = cfg
        self.root_dir = root_dir

    def _make_export(self, export_name, value):
        escaped_val = sh.shellquote(value)
        full_line = "export %s=%s" % (export_name, escaped_val)
        return full_line

    def _make_dict_export(self, kvs):
        lines = list()
        for var_name in sorted(kvs.keys()):
            var_value = kvs.get(var_name)
            if var_value is not None:
                lines.append(self._make_export(var_name, str(var_value)))
        return lines

    def _get_ec2_envs(self):
        to_set = dict()
        ip = self.cfg.get('host', 'ip')
        ec2_url_default = urlunparse(('http', "%s:%s" % (ip, EC2_PORT), "services/Cloud", '', '', ''))
        to_set['EC2_URL'] = self.cfg.getdefaulted('extern', 'ec2_url', ec2_url_default)
        s3_url_default = urlunparse(('http', "%s:%s" % (ip, S3_PORT), "services/Cloud", '', '', ''))
        to_set['S3_URL'] = self.cfg.getdefaulted('extern', 's3_url', s3_url_default)
        to_set['EC2_CERT'] = self.cfg.get('extern', 'ec2_cert_fn')
        to_set['EC2_USER_ID'] = self.cfg.get('extern', 'ec2_user_id')
        return to_set

    def _generate_ec2_env(self):
        lines = list()
        lines.append('# EC2 and/or S3 stuff')
        lines.extend(self._make_dict_export(self._get_ec2_envs()))
        lines.append("")
        return lines

    def _get_general_envs(self):
        to_set = dict()
        for (out_name, cfg_data) in CFG_MAKE.items():
            (section, key) = (cfg_data)
            to_set[out_name] = self.cfg.get(section, key)
        to_set[INSTALL_ROOT] = self.root_dir
        return to_set

    def _get_password_envs(self):
        to_set = dict()
        for (out_name, cfg_data) in PASSWORDS_MAKES.items():
            (section, key) = (cfg_data)
            to_set[out_name] = self.cfg.get(section, key)
        return to_set

    def _generate_passwords(self):
        lines = list()
        lines.append('# Password stuff')
        lines.extend(self._make_dict_export(self._get_password_envs()))
        lines.append("")
        return lines

    def _generate_general(self):
        lines = list()
        lines.append('# General stuff')
        lines.extend(self._make_dict_export(self._get_general_envs()))
        lines.append("")
        return lines

    def _generate_lines(self):
        lines = list()
        lines.append('# Generated on %s' % (date.rcf8222date()))
        lines.append("")
        lines.extend(self._generate_general())
        lines.extend(self._generate_passwords())
        lines.extend(self._generate_ec2_env())
        lines.extend(self._generate_nova_env())
        lines.extend(self._generate_os_env())
        lines.extend(self._generate_euca_env())
        lines.extend(self._generate_extern_inc())
        lines.extend(self._generate_misc_env())
        lines.extend(self._generate_aliases())
        return lines

    def update(self, fn):
        current_vars = RcReader().extract(fn)
        possible_vars = dict()
        possible_vars.update(self._get_general_envs())
        possible_vars.update(self._get_ec2_envs())
        possible_vars.update(self._get_password_envs())
        possible_vars.update(self._get_os_envs())
        possible_vars.update(self._get_euca_envs())
        possible_vars.update(self._get_nova_envs())
        possible_vars.update(self._get_misc_envs())
        new_vars = dict()
        updated_vars = dict()
        for (key, value) in possible_vars.items():
            if value is not None:
                if key in current_vars and (current_vars.get(key) != value):
                    updated_vars[key] = value
                elif key not in current_vars:
                    new_vars[key] = value
        if new_vars or updated_vars:
            lines = list()
            lines.append("")
            lines.append('# Updated on %s' % (date.rcf8222date()))
            lines.append("")
            if new_vars:
                lines.append('# New stuff')
                lines.extend(self._make_dict_export(new_vars))
                lines.append("")
            if updated_vars:
                lines.append('# Updated stuff')
                lines.extend(self._make_dict_export(updated_vars))
                lines.append("")
            append_contents = utils.joinlinesep(*lines)
            sh.append_file(fn, append_contents)
            return len(new_vars) + len(updated_vars)
        else:
            return 0

    def write(self, fn):
        contents = utils.joinlinesep(*self._generate_lines())
        sh.write_file(fn, contents)

    def _get_os_envs(self):
        params = khelper.get_shared_params(self.cfg)
        to_set = dict()
        to_set['OS_PASSWORD'] = params['admin_password']
        to_set['OS_TENANT_NAME'] = params['demo_tenant']
        to_set['OS_USERNAME'] = params['demo_user']
        to_set['OS_AUTH_URL'] = params['endpoints']['public']['uri']
        to_set['SERVICE_ENDPOINT'] = params['endpoints']['admin']['uri']
        return to_set

    def _get_misc_envs(self):
        to_set = dict()
        return to_set

    def _generate_misc_env(self):
        lines = list()
        lines.append('# Misc stuff')
        lines.extend(self._make_dict_export(self._get_misc_envs()))
        lines.append("")
        return lines

    def _generate_os_env(self):
        lines = list()
        lines.append('# Openstack stuff')
        lines.extend(self._make_dict_export(self._get_os_envs()))
        lines.append("")
        return lines

    def _generate_aliases(self):
        lines = list()
        lines.append('# Alias stuff')
        lines.append("")
        return lines

    def _get_euca_envs(self):
        to_set = dict()
        return to_set

    def _generate_euca_env(self):
        lines = list()
        lines.append('# Eucalyptus stuff')
        lines.extend(self._make_dict_export(self._get_euca_envs()))
        lines.append("")
        return lines

    def _get_nova_envs(self):
        to_set = dict()
        to_set['NOVA_VERSION'] = self.cfg.get('nova', 'nova_version')
        return to_set

    def _generate_nova_env(self):
        lines = list()
        lines.append('# Nova stuff')
        lines.extend(self._make_dict_export(self._get_nova_envs()))
        lines.append("")
        return lines

    def _generate_extern_inc(self):
        lines = list()
        lines.append('# External includes stuff')
        for inc_fn in EXTERN_INCLUDES:
            extern_inc = EXTERN_TPL.format(fn=inc_fn)
            lines.append(extern_inc.strip())
            lines.append('')
        lines.append("")
        return lines


class RcReader(object):
    def __init__(self):
        pass

    def _is_comment(self, line):
        if line.lstrip().startswith("#"):
            return True
        return False

    def extract(self, fn):
        extracted_vars = dict()
        contents = ''
        LOG.audit("Loading rc file %r" % (fn))
        try:
            with open(fn, 'r') as fh:
                contents = fh.read()
        except IOError as e:
            LOG.warn("Failed extracting rc file %r due to %s" % (fn, e))
            return extracted_vars
        for line in contents.splitlines():
            if self._is_comment(line):
                continue
            m = EXP_PAT.search(line)
            if m:
                key = m.group(1).strip()
                value = m.group(2).strip()
                quoted_mtch = QUOTED_PAT.match(value)
                if quoted_mtch:
                    value = quoted_mtch.group(1).decode('string_escape').strip()
                extracted_vars[key] = value
        return extracted_vars

    def load(self, fn):
        kvs = self.extract(fn)
        for (key, value) in kvs.items():
            env.set(key, value)
        return len(kvs)
