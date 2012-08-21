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

# This one doesn't keep comments but does seem to work better
import ConfigParser
from ConfigParser import (NoSectionError, NoOptionError)

import io
import re

# This one keeps comments but has some weirdness with it
import iniparse

import yaml

from anvil import env
from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

INTERP_PAT = r"\s*\$\(([\w\d]+):([\w\d]+)\)\s*"

LOG = logging.getLogger(__name__)


class StringiferMixin(object):
    def stringify(self, fn=None):
        contents = ''
        with io.BytesIO() as outputstream:
            self.write(outputstream)
            outputstream.flush()
            contents = utils.add_header(fn, outputstream.getvalue())
        return contents


class IgnoreMissingMixin(object):
    DEF_INT = 0
    DEF_FLOAT = 0.0
    DEF_BOOLEAN = False
    DEF_BASE = None

    def get(self, section, option):
        value = self.DEF_BASE
        try:
            value = super(IgnoreMissingMixin, self).get(section, option)
        except NoSectionError:
            pass
        except NoOptionError:
            pass
        return value

    def set(self, section, option, value):
        if not self.has_section(section) and section.lower() != 'default':
            self.add_section(section)
        super(IgnoreMissingMixin, self).set(section, option, value)

    def remove_option(self, section, option):
        if self.has_option(section, option):
            super(IgnoreMissingMixin, self).remove_option(section, option)

    def getboolean(self, section, option):
        if not self.has_option(section, option):
            return self.DEF_BOOLEAN
        return super(IgnoreMissingMixin, self).getboolean(section, option)

    def getfloat(self, section, option):
        if not self.has_option(section, option):
            return self.DEF_FLOAT
        return super(IgnoreMissingMixin, self).getfloat(section, option)

    def getint(self, section, option):
        if not self.has_option(section, option):
            return self.DEF_INT
        return super(IgnoreMissingMixin, self).getint(section, option)


class BuiltinConfigParser(IgnoreMissingMixin, ConfigParser.RawConfigParser, StringiferMixin):
    def __init__(self, cs=True, fns=None, defaults=None):
        ConfigParser.RawConfigParser.__init__(self, defaults=defaults)
        if cs:
            # Make option names case sensitive
            # See: http://docs.python.org/library/configparser.html#ConfigParser.RawConfigParser.optionxform
            self.optionxform = str
        if fns:
            for f in fns:
                self.read(f)


class RewritableConfigParser(IgnoreMissingMixin, iniparse.RawConfigParser, StringiferMixin):
    def __init__(self, cs=True, fns=None, defaults=None):
        iniparse.RawConfigParser.__init__(self, defaults=defaults)
        if cs:
            # Make option names case sensitive
            # See: http://docs.python.org/library/configparser.html#ConfigParser.RawConfigParser.optionxform
            self.optionxform = str
        if fns:
            for f in fns:
                self.read(f)


class EnvLookupDict(dict):
    def __init__(self,*args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.env_prefix = kwargs.get('env_prefix')
        if self.env_prefix is not None:
            self.env_prefix = str(self.env_prefix).upper().replace("-", "_").strip()

    def _lookup_env_key(self, key):
        if self.env_prefix is not None and key:
            env_key = self.env_prefix
            env_key += str(key).upper().replace("-", "_").strip()
            env_val = env.get_key(env_key)
            if env_val is not None:
                return str(env_val)
        return None

    def __getitem__(self, key):
        env_value = self._lookup_env_key(key)
        if env_value is not None:
            return env_value
        return dict.__getitem__(self, key)

    def get(self, key):
        env_value = self._lookup_env_key(key)
        if env_value is not None:
            return env_value
        return dict.get(self, key)


class YamlInterpolator(object):
    def __init__(self, base):
        self.in_progress = {}
        self.interpolated = {}
        self.base = base

    def _interpolate_iterable(self, what, path):
        n_what = []
        for v in what:
            n_what.append(self._interpolate(v, path))
        return n_what

    def _interpolate_dictionary(self, what, path):
        n_what = EnvLookupDict(env_prefix="_".join(path))
        for (k, v) in what.iteritems():
            path.append(k)
            n_what[k] = self._interpolate(v, path)
            path.pop()
        return n_what

    def _interpolate(self, v, path):
        n_v = v
        if v and isinstance(v, (basestring, str)):
            n_v = self._interpolate_string(v)
        elif isinstance(v, dict):
            n_v = self._interpolate_dictionary(v, path)
        elif isinstance(v, (list, set, tuple)):
            n_v = self._interpolate_iterable(v, path)
        return n_v
    
    def _interpolate_string(self, what):
        if not re.search(INTERP_PAT, what):
            return what

        def replacer(match):
            who = match.group(1).strip()
            key = match.group(2).strip()
            special_val = self._interpolate_special(who, key)
            if special_val is not None:
                return str(special_val)
            if who in self.interpolated:
                return str(self.interpolated[who][key])
            if who in self.in_progress:
                return str(self.in_progress[who][key])
            contents = self.extract(who)
            return str(contents[key])

        return re.sub(INTERP_PAT, replacer, what)

    def _interpolate_special(self, who, key):
        if key == 'ip' and who == 'auto':
            return utils.get_host_ip()
        if key == 'user' and who == 'auto':
            return sh.getuser()
        if who == 'auto':
            raise KeyError("Unknown auto key type %s" % (key))
        return None

    def extract(self, root):
        if root in self.interpolated:
            return self.interpolated[root]
        pth = sh.joinpths(self.base, "%s.yaml" % (root))
        if not sh.isfile(pth):
            return {}
        self.in_progress[root] = yaml.load(sh.load_file(pth))
        interped = self._interpolate(self.in_progress[root], path=["%s_" % (root)])
        del(self.in_progress[root])
        self.interpolated[root] = interped
        # Do a final run over the interpolated to pick up any stragglers
        # that were recursively 'included' (but not filled in)
        for (tmp_root, contents) in self.interpolated.items():
            self.interpolated[tmp_root] = self._interpolate(contents, path=["%s_" % (tmp_root)])
        return self.interpolated[root]
