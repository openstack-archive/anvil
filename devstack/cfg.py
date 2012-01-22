# vim: tabstop=4 shiftwidth=4 softtabstop=4

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
from devstack import shell as sh
from devstack import utils

LOG = logging.getLogger("devstack.cfg")
PW_TMPL = "Enter a password for %s: "
ENV_PAT = re.compile(r"^\s*\$\{([\w\d]+):\-(.*)\}\s*$")
CACHE_MSG = "(value will now be internally cached)"


class IgnoreMissingConfigParser(ConfigParser.RawConfigParser):
    DEF_INT = 0
    DEF_FLOAT = 0.0
    DEF_BOOLEAN = False

    def __init__(self):
        ConfigParser.RawConfigParser.__init__(self, allow_no_value=True)

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
        if(value == None):
            #not there so don't let the parent blowup
            return IgnoreMissingConfigParser.DEF_BOOLEAN
        return ConfigParser.RawConfigParser.getboolean(self, section, option)

    def getfloat(self, section, option):
        value = self.get(section, option)
        if(value == None):
            #not there so don't let the parent blowup
            return IgnoreMissingConfigParser.DEF_FLOAT
        return ConfigParser.RawConfigParser.getfloat(self, section, option)

    def getint(self, section, option):
        value = self.get(section, option)
        if(value == None):
            #not there so don't let the parent blowup
            return IgnoreMissingConfigParser.DEF_INT
        return ConfigParser.RawConfigParser.getint(self, section, option)


class EnvConfigParser(ConfigParser.RawConfigParser):
    def __init__(self):
        ConfigParser.RawConfigParser.__init__(self, allow_no_value=True)
        self.pws = dict()
        self.configs_fetched = dict()
        self.db_dsns = dict()

    def _makekey(self, section, option):
        parts = [section, option]
        return "/".join(parts)

    def get(self, section, option):
        key = self._makekey(section, option)
        v = None
        if(key in self.configs_fetched):
            v = self.configs_fetched.get(key)
            LOG.debug("Fetched cached value \"%s\" for param \"%s\"" % (v, key))
        else:
            LOG.debug("Fetching value for param \"%s\"" % (key))
            v = self._get_special(section, option)
            LOG.debug("Fetched \"%s\" for \"%s\"" % (v, key))
            self.configs_fetched[key] = v
        return v

    def _get_special(self, section, option):
        key = self._makekey(section, option)
        v = ConfigParser.RawConfigParser.get(self, section, option)
        if(v == None):
            return v
        mtch = ENV_PAT.match(v)
        if(mtch):
            key = mtch.group(1).strip()
            defv = mtch.group(2)
            if(len(defv) == 0 and len(key) == 0):
                msg = "Invalid bash-like value \"%s\" for \"%s\"" % (v, key)
                raise excp.BadParamException(msg)
            if(len(key) == 0):
                v = defv
                LOG.debug("Using config provided value \"%s\" for \"%s\" (no environment key)" % (v, key))
            else:
                v = env.get_key(key)
                if(v == None):
                    v = defv
                    LOG.debug("Using config provided value \"%s\" for \"%s\"" % (v, key))
            return v
        else:
            return v

    def get_host_ip(self):
        host_ip = self.get('default', 'host_ip')
        if(not host_ip):
            LOG.debug("Host ip from configuration/environment was empty, programatically attempting to determine it.")
            host_ip = utils.get_host_ip()
        key = self._makekey('default', 'host_ip')
        self.configs_fetched[key] = host_ip
        LOG.debug("Determined host ip to be: \"%s\"" % (host_ip))
        return host_ip

    def get_dbdsn(self, dbname):
        user = self.get("db", "sql_user")
        host = self.get("db", "sql_host")
        port = self.get("db", "port")
        pw = self.getpw("passwords", "sql")
        #check the dsn cache
        if(dbname in self.db_dsns):
            return self.db_dsns[dbname]
        #form the dsn (from components we have...)
        #dsn = "<driver>://<username>:<password>@<host>:<port>/<database>"
        if(not host):
            msg = "Unable to fetch a database dsn - no host found"
            raise excp.BadParamException(msg)
        driver = self.get("db", "type")
        if(not driver):
            msg = "Unable to fetch a database dsn - no driver type found"
            raise excp.BadParamException(msg)
        dsn = driver + "://"
        if(user):
            dsn += user
        if(pw):
            dsn += ":" + pw
        if(user or pw):
            dsn += "@"
        dsn += host
        if(port):
            dsn += ":" + port
        if(dbname):
            dsn += "/" + dbname
        else:
            dsn += "/"
        LOG.debug("For database \"%s\" fetched dsn \"%s\" %s" % (dbname, dsn, CACHE_MSG))
        #store for later...
        self.db_dsns[dbname] = dsn
        return dsn

    def getpw(self, section, option):
        key = self._makekey(section, option)
        pw = self.pws.get(key)
        if(pw != None):
            return pw
        pw = self.get(section, option)
        if(pw == None):
            pw = ""
        if(len(pw) == 0):
            LOG.debug("Being forced to ask for password for \"%s\" since the configuration/environment value is empty.", key)
            while(len(pw) == 0):
                pw = sh.password(PW_TMPL % (key))
        LOG.debug("Password for \"%s\" will be \"%s\" %s" % (key, pw, CACHE_MSG))
        self.pws[key] = pw
        return pw
