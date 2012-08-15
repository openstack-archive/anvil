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


from anvil import colorizer
from anvil import exceptions as excp
from anvil import log
from anvil import utils

LOG = log.getLogger(__name__)

# Used as a generic error message
BASE_ERROR = 'Currently we do not know how to %r for database type %r'

# PW keys we warm up so u won't be prompted later
PASSWORD_PROMPT = 'the database user'


def drop_db(cfg, distro, dbname):
    dbtype = cfg.get("db", "type")
    dropcmd = distro.get_command(dbtype, 'drop_db', silent=True)
    if dropcmd:
        LOG.info('Dropping %s database: %s', colorizer.quote(dbtype), colorizer.quote(dbname))
        params = dict()
        params['PASSWORD'] = cfg.get_password("sql", PASSWORD_PROMPT)
        params['USER'] = cfg.getdefaulted("db", "sql_user", 'root')
        params['DB'] = dbname
        cmds = list()
        cmds.append({
            'cmd': dropcmd,
            'run_as_root': False,
        })
        utils.execute_template(*cmds, params=params)
    else:
        msg = BASE_ERROR % ('drop', dbtype)
        raise NotImplementedError(msg)


def create_db(cfg, distro, dbname, utf8=False):
    dbtype = cfg.get("db", "type")
    if not utf8:
        createcmd = distro.get_command(dbtype, 'create_db', silent=True)
    else:
        createcmd = distro.get_command(dbtype, 'create_db_utf8', silent=True)
    if createcmd:
        LOG.info('Creating %s database: %s', colorizer.quote(dbtype), colorizer.quote(dbname))
        params = dict()
        params['PASSWORD'] = cfg.get_password("sql", PASSWORD_PROMPT)
        params['USER'] = cfg.getdefaulted("db", "sql_user", 'root')
        params['DB'] = dbname
        cmds = list()
        cmds.append({
            'cmd': createcmd,
            'run_as_root': False,
        })
        utils.execute_template(*cmds, params=params)
    else:
        msg = BASE_ERROR % ('create', dbtype)
        raise NotImplementedError(msg)


def grant_permissions(cfg, distro, user, restart_func=None):
    """
    Grant permissions on the database.
    """
    dbtype = cfg.get("db", "type")
    dbactions = distro.get_command_config(dbtype, quiet=True)
    if dbactions:
        grant_cmd = distro.get_command(dbtype, 'grant_all')
        if grant_cmd:
            if restart_func:
                LOG.info("Ensuring the database is started")
                restart_func()
            params = {
                'PASSWORD': cfg.get_password("sql", PASSWORD_PROMPT),
                'USER': user,
            }
            cmds = [{'cmd': grant_cmd}]
            LOG.info("Giving user %s full control of all databases.", colorizer.quote(user))
            utils.execute_template(*cmds, params=params)
    return


def fetch_dbdsn(cfg, dbname, utf8=False):
    """Return the database connection string, including password."""
    user = cfg.get("db", "sql_user")
    host = cfg.get("db", "sql_host")
    port = cfg.get("db", "port")
    pw = cfg.get_password("sql", PASSWORD_PROMPT)
    # Form the dsn (from components we have...)
    # dsn = "<driver>://<username>:<password>@<host>:<port>/<database>"
    # See: http://en.wikipedia.org/wiki/Data_Source_Name
    if not host:
        msg = "Unable to fetch a database dsn - no sql host found"
        raise excp.BadParamException(msg)
    driver = cfg.get("db", "type")
    if not driver:
        msg = "Unable to fetch a database dsn - no db driver type found"
        raise excp.BadParamException(msg)
    dsn = str(driver) + "://"
    if user:
        dsn += str(user)
    if pw:
        dsn += ":" + str(pw)
    if user or pw:
        dsn += "@"
    dsn += str(host)
    if port:
        dsn += ":" + str(port)
    if dbname:
        dsn += "/" + str(dbname)
        if utf8:
            # WHY U NOT SET EVERYWHERE...
            dsn += "?charset=utf8"
    else:
        dsn += "/"
    LOG.debug("For database %r fetched dsn %r" % (dbname, dsn))
    return dsn
