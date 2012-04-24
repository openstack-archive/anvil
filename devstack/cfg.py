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

import io
import re

import iniparse

from devstack import cfg_helpers
from devstack import date
from devstack import env
from devstack import exceptions as excp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

LOG = logging.getLogger("devstack.cfg")
ENV_PAT = re.compile(r"^\s*\$\{([\w\d]+):\-(.*)\}\s*$")
SUB_MATCH = re.compile(r"(?:\$\(([\w\d]+):([\w\d]+))\)")


class IgnoreMissingConfigParser(iniparse.RawConfigParser):
    DEF_INT = 0
    DEF_FLOAT = 0.0
    DEF_BOOLEAN = False
    DEF_BASE = None

    def __init__(self, cs=True, fns=None):
        iniparse.RawConfigParser.__init__(self)
        if cs:
            # Make option names case sensitive
            # See: http://docs.python.org/library/configparser.html#ConfigParser.RawConfigParser.optionxform
            self.optionxform = str
        if fns:
            for f in fns:
                self.read(f)

    def get(self, section, option):
        value = self.DEF_BASE
        try:
            value = iniparse.RawConfigParser.get(self, section, option)
        except iniparse.NoSectionError:
            pass
        except iniparse.NoOptionError:
            pass
        return value

    def set(self, section, option, value):
        if not self.has_section(section) and section.lower() != 'default':
            self.add_section(section)
        iniparse.RawConfigParser.set(self, section, option, value)

    def remove_option(self, section, option):
        if self.has_option(section, option):
            iniparse.RawConfigParser.remove_option(self, section, option)

    def getboolean(self, section, option):
        if not self.has_option(section, option):
            return self.DEF_BOOLEAN
        return iniparse.RawConfigParser.getboolean(self, section, option)

    def getfloat(self, section, option):
        if not self.has_option(section, option):
            return self.DEF_FLOAT
        return iniparse.RawConfigParser.getfloat(self, section, option)

    def getint(self, section, option):
        if not self.has_option(section, option):
            return self.DEF_INT
        return iniparse.RawConfigParser.getint(self, section, option)

    def stringify(self, fn=None):
        contents = ''
        with io.BytesIO() as outputstream:
            self.write(outputstream)
            outputstream.flush()
            contents = utils.add_header(fn, outputstream.getvalue())
        return contents


class ProxyConfig(object):

    def __init__(self, cache_enabled=True):
        self.read_resolvers = []
        self.set_resolvers = []
        self.cache_enabled = cache_enabled
        self.cache = dict()

    def add_read_resolver(self, resolver):
        self.read_resolvers.append(resolver)

    def add_set_resolver(self, resolver):
        self.set_resolvers.append(resolver)

    def get(self, section, option):
        # Try the cache first
        cache_key = None
        if self.cache_enabled:
            cache_key = cfg_helpers.make_id(section, option)
            if cache_key in self.cache:
                return self.cache[cache_key]
        # Check the resolvers
        val = None
        for resolver in self.read_resolvers:
            LOG.debug("Looking for %r using resolver %s", cfg_helpers.make_id(section, option), resolver)
            val = resolver.get(section, option)
            if val is not None:
                LOG.debug("Found value %r for %r using resolver %s", cfg_helpers.make_id(section, option), val, resolver)
                break
        if self.cache_enabled:
            self.cache[cache_key] = val
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

    def pprint(self, group_by, order_by):
        """
        Dumps the given config key value cache in the
        order that stack is defined to group that cache
        in a nice and pretty manner.

        Arguments:
            config_cache: map of items to group and then pretty print
        """
        if not self.cache_enabled:
            return

        LOG.debug("Grouping by %s", group_by.keys())
        LOG.debug("Ordering by %s", order_by)

        def item_format(key, value):
            return "\t%s=%s" % (str(key), str(value))

        def map_print(mp):
            for key in sorted(mp.keys()):
                value = mp.get(key)
                LOG.info(item_format(key, value))

        # First partition into our groups
        partitions = dict()
        for name in group_by.keys():
            partitions[name] = dict()

        # Now put the config cached values into there partitions
        for (k, v) in self.cache.items():
            for name in order_by:
                entries = partitions[name]
                if k.startswith(name):
                    entries[k] = v
                    break

        # Now print them..
        for name in order_by:
            nice_name = group_by.get(name)
            LOG.info(nice_name + ":")
            entries = partitions.get(name)
            if entries:
                map_print(entries)

    def set(self, section, option, value):
        for resolver in self.set_resolvers:
            LOG.debug("Setting %r to %s using resolver %s", cfg_helpers.make_id(section, option), value, resolver)
            resolver.set(section, option, value)
        if self.cache_enabled:
            cache_key = cfg_helpers.make_id(section, option)
            self.cache[cache_key] = value


class ConfigResolver(object):

    def __init__(self, backing):
        self.backing = backing

    def get(self, section, option):
        return self.backing.get(section, option)

    def set(self, section, option, value):
        self.backing.set(section, option, value)


class DynamicResolver(ConfigResolver):

    def get(self, section, option):
        return self._resolve_value(section, option, ConfigResolver.get(self, section, option))

    def _resolve_value(self, section, option, value_gotten):
        if section == 'host' and option == 'ip':
            LOG.debug("Host ip from configuration/environment was empty, programatically attempting to determine it.")
            value_gotten = utils.get_host_ip()
            LOG.debug("Determined your host ip to be: %r" % (value_gotten))
        return value_gotten


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
                LOG.warn("Badly formatted cli option: %r", c)
            else:
                section = (split_up[0]).strip()
                if not section or section.lower() == 'default':
                    section = 'DEFAULT'
                option = split_up[1].strip()
                value = split_up[2]
                parsed_args[cfg_helpers.make_id(section, option)] = value
        return cls(parsed_args)


class EnvResolver(DynamicResolver):

    def get(self, section, option):
        return self._resolve_value(section, option, self._get_bashed(section, option))

    def _getdefaulted(self, section, option, default_value):
        val = self.get(section, option)
        if not val or not val.strip():
            return default_value
        return val

    def _get_bashed(self, section, option):
        value = DynamicResolver.get(self, section, option)
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
