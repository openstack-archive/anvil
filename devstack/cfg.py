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

import iniparse as ConfigParser

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
CACHE_MSG = "(value will now be internally cached)"


def get_config(cfg_fn=None):
    if not cfg_fn:
        cfg_fn = sh.canon_path(settings.STACK_CONFIG_LOCATION)
    config_instance = StackConfigParser()
    config_instance.read(cfg_fn)
    return config_instance


class IgnoreMissingConfigParser(ConfigParser.RawConfigParser):
    DEF_INT = 0
    DEF_FLOAT = 0.0
    DEF_BOOLEAN = False
    DEF_BASE = None

    def __init__(self, cs=True, fns=None):
        ConfigParser.RawConfigParser.__init__(self)
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
            value = ConfigParser.RawConfigParser.get(self, section, option)
        except ConfigParser.NoSectionError:
            pass
        except ConfigParser.NoOptionError:
            pass
        return value

    def set(self, section, option, value):
        if not self.has_section(section) and section.lower() != 'default':
            self.add_section(section)
        ConfigParser.RawConfigParser.set(self, section, option, value)

    def remove_option(self, section, option):
        if self.has_option(section, option):
            ConfigParser.RawConfigParser.remove_option(self, section, option)

    def getboolean(self, section, option):
        if not self.has_option(section, option):
            return self.DEF_BOOLEAN
        return ConfigParser.RawConfigParser.getboolean(self, section, option)

    def getfloat(self, section, option):
        if not self.has_option(section, option):
            return self.DEF_FLOAT
        return ConfigParser.RawConfigParser.getfloat(self, section, option)

    def getint(self, section, option):
        if not self.has_option(section, option):
            return self.DEF_INT
        return ConfigParser.RawConfigParser.getint(self, section, option)
    
    def stringify(self, fn=None):
        contents = ''
        with io.BytesIO() as outputstream:
            self.write(outputstream)
            outputstream.flush()
            contents = add_header(fn, outputstream.getvalue())
        return contents


class StackConfigParser(IgnoreMissingConfigParser):
    def __init__(self, cs=True):
        IgnoreMissingConfigParser.__init__(self, cs)
        self.configs_fetched = dict()

    def _resolve_value(self, section, option, value_gotten):
        if section == 'host' and option == 'ip':
            LOG.debug("Host ip from configuration/environment was empty, programatically attempting to determine it.")
            value_gotten = utils.get_host_ip()
            LOG.debug("Determined your host ip to be: %r" % (value_gotten))
        return value_gotten

    def getdefaulted(self, section, option, default_val):
        val = self.get(section, option)
        if not val or not val.strip():
            LOG.debug("Value %r found was not good enough, returning provided default '%s'" % (val, default_val))
            return default_val
        return val

    def get(self, section, option):
        key = cfg_helpers.make_id(section, option)
        if key in self.configs_fetched:
            value = self.configs_fetched.get(key)
            LOG.debug("Fetched cached value '%s' for param %r" % (value, key))
        else:
            LOG.debug("Fetching value for param %r" % (key))
            gotten_value = self._get_bashed(section, option)
            value = self._resolve_value(section, option, gotten_value)
            LOG.debug("Fetched %r for %r %s" % (value, key, CACHE_MSG))
            self.configs_fetched[key] = value
        return value

    def set(self, section, option, value):
        key = cfg_helpers.make_id(section, option)
        LOG.audit("Setting config value '%s' for param %r" % (value, key))
        self.configs_fetched[key] = value
        IgnoreMissingConfigParser.set(self, section, option, value)

    def _resolve_replacements(self, value):
        LOG.debug("Performing simple replacement on %r", value)

        #allow for our simple replacement to occur
        def replacer(match):
            section = match.group(1)
            option = match.group(2)
            return self.getdefaulted(section, option, '')

        return SUB_MATCH.sub(replacer, value)

    def _get_bashed(self, section, option):
        value = IgnoreMissingConfigParser.get(self, section, option)
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


def add_header(fn, contents):
    lines = list()
    if not fn:
        fn = "???"
    lines.append('# Adjusted source file %s' % (fn.strip()))
    lines.append("# On %s" % (date.rcf8222date()))
    lines.append("# By user %s, group %s" % (sh.getuser(), sh.getgroupname()))
    lines.append("")
    if contents:
        lines.append(contents)
    return utils.joinlinesep(*lines)
