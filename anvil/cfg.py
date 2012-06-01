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
from ConfigParser import (DuplicateSectionError, NoSectionError, NoOptionError)
                  
import collections
import io
import re

# This one keeps comments but has some weirdness with it
import iniparse

try:
    # Only exists on 2.7 or greater
    from collections import OrderedDict
except ImportError:
    try:
        # Try the pypi module
        from ordereddict import OrderedDict
    except ImportError:
        # Not really ordered :-(
        OrderedDict = dict

from anvil import cfg_helpers
from anvil import env
from anvil import exceptions as excp
from anvil import log as logging
from anvil import utils

ENV_PAT = re.compile(r"^\s*\$\{([\w\d]+):\-(.*)\}\s*$")
SUB_MATCH = re.compile(r"(?:\$\(([\w\d]+):([\w\d]+))\)")

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
        ConfigParser.RawConfigParser.__init__(self, defaults=defaults, dict_type=OrderedDict)
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


class ProxyConfig(object):

    def __init__(self):
        self.read_resolvers = []
        self.set_resolvers = []
        self.opts_cache = dict()
        self.opts_read = dict()
        self.opts_set = dict()
        self.pw_resolvers = []

    def add_password_resolver(self, resolver):
        self.pw_resolvers.append(resolver)

    def add_read_resolver(self, resolver):
        self.read_resolvers.append(resolver)

    def add_set_resolver(self, resolver):
        self.set_resolvers.append(resolver)

    def get_password(self, option, prompt_text='', length=8, **kwargs):
        password = ''
        for resolver in self.pw_resolvers:
            LOG.debug("Looking up password for %s using instance %s", option, resolver)
            found_password = resolver.get_password(option,
                                                prompt_text=prompt_text,
                                                length=length, **kwargs)
            if found_password is not None and len(found_password):
                password = found_password
                break
        if len(password) == 0:
            LOG.warn("Password provided for %r is empty", option)
        self.set(cfg_helpers.PW_SECTION, option, password)
        return password

    def get(self, section, option):
        # Try the cache first
        cache_key = cfg_helpers.make_id(section, option)
        if cache_key in self.opts_cache:
            return self.opts_cache[cache_key]
        # Check the resolvers
        val = None
        for resolver in self.read_resolvers:
            LOG.debug("Looking for %r using resolver %s", cfg_helpers.make_id(section, option), resolver)
            found_val = resolver.get(section, option)
            if found_val is not None:
                LOG.debug("Found value %r for section %r using resolver %s", found_val, cfg_helpers.make_id(section, option), resolver)
                val = found_val
                break
        # Store in cache if we found something
        if val is not None:
            self.opts_cache[cache_key] = val
        # Mark as read
        if section not in self.opts_read:
            self.opts_read[section] = set()
        self.opts_read[section].add(option)
        return val

    def getdefaulted(self, section, option, default_value=''):
        val = self.get(section, option)
        if not val or not val.strip():
            return default_value
        return val

    def getfloat(self, section, option):
        try:
            return float(self.get(section, option))
        except ValueError:
            return None

    def getint(self, section, option):
        try:
            return int(self.get(section, option))
        except ValueError:
            return None

    def getboolean(self, section, option):
        return utils.make_bool(self.getdefaulted(section, option))

    def set(self, section, option, value):
        for resolver in self.set_resolvers:
            LOG.debug("Setting %r to %s using resolver %s", cfg_helpers.make_id(section, option), value, resolver)
            resolver.set(section, option, value)
        cache_key = cfg_helpers.make_id(section, option)
        self.opts_cache[cache_key] = value
        if section not in self.opts_set:
            self.opts_set[section] = set()
        self.opts_set[section].add(option)
        return value


class ConfigResolver(object):

    def __init__(self, backing):
        self.backing = backing

    def get(self, section, option):
        return self._resolve_value(section, option, self._get_bashed(section, option))

    def set(self, section, option, value):
        self.backing.set(section, option, value)

    def _resolve_value(self, section, option, value_gotten):
        if not value_gotten:
            if section == 'host' and option == 'ip':
                LOG.debug("Host ip from configuration/environment was empty, programatically attempting to determine it.")
                value_gotten = utils.get_host_ip()
                LOG.debug("Determined your host ip to be: %r" % (value_gotten))
        return value_gotten

    def _getdefaulted(self, section, option, default_value):
        val = self.get(section, option)
        if not val or not val.strip():
            return default_value
        return val

    def _get_bashed(self, section, option):
        value = self.backing.get(section, option)
        if value is None:
            return value
        extracted_val = ''
        mtch = ENV_PAT.match(value)
        if mtch:
            env_key = mtch.group(1).strip()
            def_val = mtch.group(2).strip()
            if not def_val and not env_key:
                msg = "Invalid bash-like value %r" % (value)
                raise excp.BadParamException(msg)
            LOG.debug("Looking for that value in environment variable: %r", env_key)
            env_value = env.get_key(env_key)
            if env_value is None:
                LOG.debug("Extracting value from config provided default value %r" % (def_val))
                extracted_val = self._resolve_replacements(def_val)
                LOG.debug("Using config provided default value %r (no environment key)" % (extracted_val))
            else:
                extracted_val = env_value
                LOG.debug("Using enviroment provided value %r" % (extracted_val))
        else:
            extracted_val = value
            LOG.debug("Using raw config provided value %r" % (extracted_val))
        return extracted_val

    def _resolve_replacements(self, value):
        LOG.debug("Performing simple replacement on %r", value)

        # Allow for our simple replacement to occur
        def replacer(match):
            section = match.group(1)
            option = match.group(2)
            # We use the default fetcher here so that we don't try to put in None values...
            return self._getdefaulted(section, option, '')

        return SUB_MATCH.sub(replacer, value)


class CliResolver(object):

    def __init__(self, cli_args):
        self.cli_args = cli_args

    def get(self, section, option):
        return self.cli_args.get(cfg_helpers.make_id(section, option))

    @classmethod
    def create(cls, cli_args):
        parsed_args = dict()
        for c in cli_args:
            if not c:
                continue
            split_up = c.split("/")
            if len(split_up) != 3:
                LOG.warn("Incorrectly formatted cli option: %r", c)
            else:
                section = (split_up[0]).strip()
                if not section or section.lower() == 'default':
                    section = 'DEFAULT'
                option = split_up[1].strip()
                if not option:
                    LOG.warn("Badly formatted cli option - no option name: %r", c)
                else:
                    parsed_args[cfg_helpers.make_id(section, option)] = split_up[2]
        return cls(parsed_args)


class EnvResolver(object):

    def __init__(self):
        pass

    def _form_key(self, section, option):
        return cfg_helpers.make_id(section, option)

    def get(self, section, option):
        return env.get_key(self._form_key(section, option))
