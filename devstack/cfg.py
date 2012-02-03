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
import ConfigParser

from devstack import env
from devstack import exceptions as excp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils


LOG = logging.getLogger("devstack.cfg")
PW_TMPL = "Enter a password for %s: "
ENV_PAT = re.compile(r"^\s*\$\{([\w\d]+):\-(.*)\}\s*$")
SUB_MATCH = re.compile(r"(?:\$\(([\w\d]+):([\w\d]+))\)")
CACHE_MSG = "(value will now be internally cached)"
DEF_PW_MSG = "[or press enter to get a generated one]"
PW_PROMPTS = {
    'horizon_keystone_admin': "Enter a password to use for horizon and keystone (20 chars or less) %s: " % (DEF_PW_MSG),
    'service_token': 'Enter a token to use for the service admin token %s: ' % (DEF_PW_MSG),
    'sql': 'Enter a password to use for your sql database user %s: ' % (DEF_PW_MSG),
    'rabbit': 'Enter a password to use for your rabbit user %s: ' % (DEF_PW_MSG),
}


class StackConfigParser(ConfigParser.RawConfigParser):
    def __init__(self):
        ConfigParser.RawConfigParser.__init__(self)
        self.pws = dict()
        self.configs_fetched = dict()
        self.db_dsns = dict()

    def _makekey(self, section, option):
        return "/".join([str(section), str(option)])

    def _resolve_special(self, section, option, value_gotten):
        if value_gotten and len(value_gotten):
            if section == 'passwords':
                #ensure we store it as a password
                key = self._makekey(section, option)
                self.pws[key] = value_gotten
            return value_gotten
        if section == 'host' and option == 'ip':
            LOG.debug("Host ip from configuration/environment was empty, programatically attempting to determine it.")
            netifc = self.get("default", "net_interface") or "eth0"
            netifcs = [netifc.strip(), 'br100']
            host_ip, netifc = utils.get_host_ip(netifcs, settings.IPV4)
            LOG.debug("Determined host ip to be: \"%s\" from network interface: %s" % (host_ip, netifc))
            return host_ip
        elif section == 'passwords':
            key = self._makekey(section, option)
            LOG.debug("Being forced to ask for password for \"%s\" since the configuration/environment value is empty.", key)
            prompt = PW_PROMPTS.get(option)
            if not prompt:
                prompt = PW_TMPL % (key)
            pw = sh.password(prompt)
            self.pws[key] = pw
            return pw
        else:
            return value_gotten

    def get(self, section, option):
        key = self._makekey(section, option)
        value = None
        if key in self.configs_fetched:
            value = self.configs_fetched.get(key)
            LOG.debug("Fetched cached value \"%s\" for param \"%s\"" % (value, key))
        else:
            LOG.debug("Fetching value for param \"%s\"" % (key))
            gotten_value = self._get_special(section, option)
            value = self._resolve_special(section, option, gotten_value)
            LOG.debug("Fetched \"%s\" for \"%s\"" % (value, key))
            self.configs_fetched[key] = value
        return value

    def _extract_default(self, default_value):
        if not SUB_MATCH.search(default_value):
            return default_value

        LOG.debug("Performing simple replacement on %s", default_value)

        #allow for our simple replacement to occur
        def replacer(match):
            section = match.group(1)
            option = match.group(2)
            return self.get(section, option)

        return SUB_MATCH.sub(replacer, default_value)

    def _get_special(self, section, option):
        key = self._makekey(section, option)
        parent_val = ConfigParser.RawConfigParser.get(self, section, option)
        if parent_val is None:
            #parent didn't have anything, we are unable to do anything with it then
            return None
        extracted_val = None
        mtch = ENV_PAT.match(parent_val)
        if mtch:
            env_key = mtch.group(1).strip()
            def_val = mtch.group(2)
            if not def_val and not env_key:
                msg = "Invalid bash-like value \"%s\" for \"%s\"" % (parent_val, key)
                raise excp.BadParamException(msg)
            if not env_key or env.get_key(env_key) is None:
                LOG.debug("Extracting default value from config provided default value \"%s\" for \"%s\"" % (def_val, key))
                actual_def_val = self._extract_default(def_val)
                LOG.debug("Using config provided default value \"%s\" for \"%s\" (no environment key)" % (actual_def_val, key))
                extracted_val = actual_def_val
            else:
                env_val = env.get_key(env_key)
                LOG.debug("Using enviroment provided value \"%s\" for \"%s\"" % (env_val, key))
                extracted_val = env_val
        else:
            LOG.debug("Using raw config provided value \"%s\" for \"%s\"" % (parent_val, key))
            extracted_val = parent_val
        return extracted_val

    def get_dbdsn(self, dbname):
        #check the dsn cache
        if dbname in self.db_dsns:
            return self.db_dsns[dbname]
        user = self.get("db", "sql_user")
        host = self.get("db", "sql_host")
        port = self.get("db", "port")
        pw = self.get("passwords", "sql")
        #form the dsn (from components we have...)
        #dsn = "<driver>://<username>:<password>@<host>:<port>/<database>"
        if not host:
            msg = "Unable to fetch a database dsn - no host found"
            raise excp.BadParamException(msg)
        driver = self.get("db", "type")
        if not driver:
            msg = "Unable to fetch a database dsn - no driver type found"
            raise excp.BadParamException(msg)
        dsn = driver + "://"
        if user:
            dsn += user
        if pw:
            dsn += ":" + pw
        if user or pw:
            dsn += "@"
        dsn += host
        if port:
            dsn += ":" + port
        if dbname:
            dsn += "/" + dbname
        else:
            dsn += "/"
        LOG.debug("For database \"%s\" fetched dsn \"%s\" %s" % (dbname, dsn, CACHE_MSG))
        #store for later...
        self.db_dsns[dbname] = dsn
        return dsn


class IgnoreMissingConfigParser(ConfigParser.RawConfigParser):
    DEF_INT = 0
    DEF_FLOAT = 0.0
    DEF_BOOLEAN = False

    def __init__(self):
        ConfigParser.RawConfigParser.__init__(self)
        #make option names case sensitive
        self.optionxform = str

    def get(self, section, option):
        value = None
        try:
            value = ConfigParser.RawConfigParser.get(self, section, option)
        except ConfigParser.NoSectionError, e:
            pass
        except ConfigParser.NoOptionError, e:
            pass
        return value

    def getboolean(self, section, option):
        value = self.get(section, option)
        if value is None:
            #not there so don't let the parent blowup
            return IgnoreMissingConfigParser.DEF_BOOLEAN
        return ConfigParser.RawConfigParser.getboolean(self, section, option)

    def getfloat(self, section, option):
        value = self.get(section, option)
        if value is None:
            #not there so don't let the parent blowup
            return IgnoreMissingConfigParser.DEF_FLOAT
        return ConfigParser.RawConfigParser.getfloat(self, section, option)

    def getint(self, section, option):
        value = self.get(section, option)
        if value is None:
            #not there so don't let the parent blowup
            return IgnoreMissingConfigParser.DEF_INT
        return ConfigParser.RawConfigParser.getint(self, section, option)
