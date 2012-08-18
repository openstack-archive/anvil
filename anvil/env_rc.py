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

from anvil import cfg
from anvil import colorizer
from anvil import env
from anvil import log as logging
from anvil import settings
from anvil import shell as sh
from anvil import utils

LOG = logging.getLogger(__name__)

# General extraction cfg keys + sections
CFG_MAKE = {
    'FLAT_INTERFACE': ('nova', 'flat_interface'),
    'HOST_IP': ('host', 'ip'),
}

# PW sections
PASSWORDS_MAKES = {
    'ADMIN_PASSWORD': (cfg.PW_SECTION, 'horizon_keystone_admin'),
    'SERVICE_PASSWORD': (cfg.PW_SECTION, 'service_password'),
    'RABBIT_PASSWORD': (cfg.PW_SECTION, 'rabbit'),
    'SERVICE_TOKEN': (cfg.PW_SECTION, 'service_token'),
    'MYSQL_PASSWORD': (cfg.PW_SECTION, 'sql'),
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

# Attempt to use them from other installs (devstack and such)
EXTERN_INCLUDES = ['localrc', 'eucarc']


class RcWriter(object):

    def __init__(self, cfg, root_dir, components):
        self.cfg = cfg
        self.root_dir = root_dir
        self.components = components
        self.lines = None
        self.created = 0

    def _make_export(self, export_name, value):
        self.created += 1
        return "export %s=%s" % (export_name, sh.shellquote(value))

    def _make_dict_export(self, kvs):
        lines = list()
        for var_name in sorted(kvs.keys()):
            var_value = kvs.get(var_name)
            if var_value is not None:
                lines.append(self._make_export(var_name, str(var_value)))
        return lines

    def _get_ec2_envs(self):
        to_set = {}
        ip = self.cfg.get('host', 'ip')
        ec2_url_default = urlunparse(('http', "%s:%s" % (ip, EC2_PORT), "services/Cloud", '', '', ''))
        to_set['EC2_URL'] = self.cfg.getdefaulted('extern', 'ec2_url', ec2_url_default)
        s3_url_default = urlunparse(('http', "%s:%s" % (ip, S3_PORT), "services/Cloud", '', '', ''))
        to_set['S3_URL'] = self.cfg.getdefaulted('extern', 's3_url', s3_url_default)
        return to_set

    def _generate_ec2_env(self):
        lines = []
        lines.append('# EC2 and/or S3 stuff')
        lines.extend(self._make_dict_export(self._get_ec2_envs()))
        lines.append("")
        return lines

    def _get_general_envs(self):
        to_set = {}
        for (out_name, cfg_data) in CFG_MAKE.items():
            (section, key) = (cfg_data)
            to_set[out_name] = self.cfg.get(section, key)
        to_set[INSTALL_ROOT] = self.root_dir
        return to_set

    def _get_password_envs(self):
        to_set = {}
        for (out_name, cfg_data) in PASSWORDS_MAKES.items():
            (section, key) = cfg_data
            to_set[out_name] = self.cfg.get(section, key)
        return to_set

    def _generate_passwords(self):
        lines = []
        lines.append('# Password stuff')
        lines.extend(self._make_dict_export(self._get_password_envs()))
        lines.append("")
        return lines

    def _generate_general(self):
        lines = []
        lines.append('# General stuff')
        lines.extend(self._make_dict_export(self._get_general_envs()))
        lines.append("")
        return lines

    def _generate_lines(self):
        lines = []
        lines.extend(self._generate_general())
        lines.extend(self._generate_passwords())
        lines.extend(self._generate_ec2_env())
        lines.extend(self._generate_extern_inc())
        lines.extend(self._generate_components())
        return lines

    def _generate_components(self):
        lines = []
        for (c, component) in self.components:
            there_envs = component.env_exports
            if there_envs:
                lines.append('# %s stuff' % (c.title().strip()))
                lines.extend(self._make_dict_export(there_envs))
                lines.append('')
        return lines

    def write(self, fn):
        if self.lines is None:
            self.lines = self._generate_lines()
        out_lines = list(self.lines)
        if sh.isfile(fn):
            out_lines.insert(0, '')
            out_lines.insert(0, '# Updated on %s' % (utils.rcf8222date()))
            out_lines.insert(0, '')
        else:
            out_lines.insert(0, '')
            out_lines.insert(0, '# Created on %s' % (utils.rcf8222date()))
        # Don't use sh 'lib' here so that we always
        # read this (even if dry-run)
        with open(fn, 'a') as fh:
            fh.write(utils.joinlinesep(*out_lines))

    def _generate_extern_inc(self):
        lines = []
        lines.append('# External includes stuff')
        for inc_fn in EXTERN_INCLUDES:
            extern_inc = EXTERN_TPL.format(fn=inc_fn)
            lines.append(extern_inc.strip())
            lines.append('')
        return lines


class RcReader(object):

    def _is_comment(self, line):
        if line.lstrip().startswith("#"):
            return True
        return False

    def extract(self, fn):
        contents = ''
        LOG.debug("Loading bash 'style' resource file %r", fn)
        try:
            # Don't use sh here so that we always
            # read this (even if dry-run)
            with open(fn, 'r') as fh:
                contents = fh.read()
        except IOError as e:
            return {}
        return self._dict_convert(contents)

    def _unescape_string(self, text):
        return text.decode('string_escape').strip()

    def _dict_convert(self, contents):
        extracted_vars = {}
        for line in contents.splitlines():
            if self._is_comment(line):
                continue
            m = EXP_PAT.search(line)
            if m:
                key = m.group(1).strip()
                value = m.group(2).strip()
                quoted_mtch = QUOTED_PAT.match(value)
                if quoted_mtch:
                    value = self._unescape_string(quoted_mtch.group(1))
                extracted_vars[key] = value
        return extracted_vars

    def load(self, fn):
        kvs = self.extract(fn)
        for (key, value) in kvs.items():
            env.set(key, value)
        return len(kvs)


def load(read_fns=None):
    if not read_fns:
        read_fns = [
            settings.gen_rc_filename('core'),
        ]
    loaded_am = 0
    for fn in read_fns:
        am_loaded = RcReader().load(fn)
        loaded_am += am_loaded
    return (loaded_am, read_fns)


def write(action, write_fns=None, components=None):
    if not components:
        components = []
    if not write_fns:
        write_fns = [
            settings.gen_rc_filename('core'),
        ]
    writer = RcWriter(action.cfg, action.root_dir, components)
    for fn in write_fns:
        writer.write(fn)
    return (writer.created, write_fns)
