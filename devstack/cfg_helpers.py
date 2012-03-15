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

from devstack import exceptions as excp
from devstack import log as logging
from devstack import settings

LOG = logging.getLogger("devstack.cfg.helpers")


def make_id(section, option):
    joinwhat = []
    if section is not None:
        joinwhat.append(str(section))
    if option is not None:
        joinwhat.append(str(option))
    return "/".join(joinwhat)


def fetch_run_type(config):
    run_type = config.getdefaulted("default", "run_type", settings.RUN_TYPE_DEF)
    return run_type.upper()


def fetch_dbdsn(config, pw_gen, dbname=''):
    user = config.get("db", "sql_user")
    host = config.get("db", "sql_host")
    port = config.get("db", "port")
    pw = pw_gen.get_password("sql")
    #form the dsn (from components we have...)
    #dsn = "<driver>://<username>:<password>@<host>:<port>/<database>"
    if not host:
        msg = "Unable to fetch a database dsn - no sql host found"
        raise excp.BadParamException(msg)
    driver = config.get("db", "type")
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
    LOG.audit("For database [%s] fetched dsn [%s]" % (dbname, dsn))
    return dsn
