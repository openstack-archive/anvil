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

import re
import ConfigParser

from devstack import date
from devstack import env
from devstack import exceptions as excp
from devstack import log as logging
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
    'old_sql': "Please enter your current mysql password so we that can reset it for next time: ",
}


class IgnoreMissingConfigParser(ConfigParser.RawConfigParser):
    DEF_INT = 0
    DEF_FLOAT = 0.0
    DEF_BOOLEAN = False
    DEF_STRING = ''

    def __init__(self):
        ConfigParser.RawConfigParser.__init__(self)
        #make option names case sensitive
        self.optionxform = str

    def get(self, section, option):
        value = IgnoreMissingConfigParser.DEF_STRING
        try:
            value = ConfigParser.RawConfigParser.get(self, section, option)
        except ConfigParser.NoSectionError:
            pass
        except ConfigParser.NoOptionError:
            pass
        return value

    def getboolean(self, section, option):
        if not self.has_option(section, option):
            return IgnoreMissingConfigParser.DEF_BOOLEAN
        return ConfigParser.RawConfigParser.getboolean(self, section, option)

    def getfloat(self, section, option):
        if not self.has_option(section, option):
            return IgnoreMissingConfigParser.DEF_FLOAT
        return ConfigParser.RawConfigParser.getfloat(self, section, option)

    def getint(self, section, option):
        if not self.has_option(section, option):
            return IgnoreMissingConfigParser.DEF_INT
        return ConfigParser.RawConfigParser.getint(self, section, option)


class StackConfigParser(IgnoreMissingConfigParser):
    def __init__(self):
        IgnoreMissingConfigParser.__init__(self)
        self.pws = dict()
        self.configs_fetched = dict()
        self.db_dsns = dict()

    def _makekey(self, section, option):
        joinwhat = []
        if section is not None:
            joinwhat.append(str(section))
        if option is not None:
            joinwhat.append(str(option))
        return "/".join(joinwhat)

    def _resolve_special(self, section, option, value_gotten, auto_pw):
        key = self._makekey(section, option)
        if value_gotten and len(value_gotten):
            if section == 'passwords':
                self.pws[key] = value_gotten
        elif section == 'host' and option == 'ip':
            LOG.debug("Host ip from configuration/environment was empty, programatically attempting to determine it.")
            value_gotten = utils.get_host_ip()
            LOG.debug("Determined your host ip to be: \"%s\"" % (value_gotten))
        elif section == 'passwords' and auto_pw:
            LOG.debug("Being forced to ask for password for \"%s\" since the configuration value is empty.", key)
            prompt = PW_PROMPTS.get(option, PW_TMPL % (key))
            value_gotten = sh.password(prompt)
            self.pws[key] = value_gotten
        return value_gotten

    def getdefaulted(self, section, option, default_val, auto_pw=True):
        val = self.get(section, option, auto_pw=auto_pw)
        if not val:
            return default_val
        return val

    def get(self, section, option, auto_pw=True):
        key = self._makekey(section, option)
        if key in self.configs_fetched:
            value = self.configs_fetched.get(key)
            LOG.debug("Fetched cached value \"%s\" for param \"%s\"" % (value, key))
        else:
            LOG.debug("Fetching value for param \"%s\"" % (key))
            gotten_value = self._get_special(section, option)
            value = self._resolve_special(section, option, gotten_value, auto_pw)
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
        value = IgnoreMissingConfigParser.get(self, section, option)
        extracted_val = ''
        mtch = ENV_PAT.match(value)
        if mtch:
            env_key = mtch.group(1).strip()
            def_val = mtch.group(2)
            if not def_val and not env_key:
                msg = "Invalid bash-like value \"%s\" for \"%s\"" % (value, key)
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
            LOG.debug("Using raw config provided value \"%s\" for \"%s\"" % (value, key))
            extracted_val = value
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
            msg = "Unable to fetch a database dsn - no sql host found"
            raise excp.BadParamException(msg)
        driver = self.get("db", "type")
        if not driver:
            msg = "Unable to fetch a database dsn - no db driver type found"
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


def add_header(fn, contents):
    lines = list()
    lines.append('# Adjusted source file %s' % (fn.strip()))
    lines.append("# On %s" % (date.rcf8222date()))
    lines.append("# By user %s, group %s" % (sh.getuser(), sh.getgroupname()))
    lines.append("# Comments may have been removed (TODO: darn python config writer)")
    # TODO Maybe use https://code.google.com/p/iniparse/ which seems to preserve comments!
    lines.append("")
    if contents:
        lines.append(contents)
    return utils.joinlinesep(*lines)
