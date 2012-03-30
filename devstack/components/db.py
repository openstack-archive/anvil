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

from devstack import component as comp
from devstack import exceptions as excp
from devstack import log as logging
from devstack import shell as sh
from devstack import utils

import abc

LOG = logging.getLogger("devstack.components.db")

# Need to reset pw to blank since this distributions don't seem to
# always reset it when u uninstall the db
RESET_BASE_PW = ''

# Links about how to reset if we fail to set the PW
SQL_RESET_PW_LINKS = [
    'https://help.ubuntu.com/community/MysqlPasswordReset',
    'http://dev.mysql.com/doc/refman/5.0/en/resetting-permissions.html',
    ]

# Used as a generic error message
BASE_ERROR = 'Currently we do not know how to %r for database type %r'

# PW keys we warm up so u won't be prompted later
PASSWORD_PROMPT = 'the database user'
WARMUP_PWS = [('sql', PASSWORD_PROMPT)]


class DBUninstaller(comp.PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgUninstallComponent.__init__(self, *args, **kargs)
        self.runtime = DBRuntime(*args, **kargs)

    def warm_configs(self):
        for key, prompt in WARMUP_PWS:
            self.pw_gen.get_password(key, prompt)

    def pre_uninstall(self):
        dbtype = self.cfg.get("db", "type")
        dbactions = self.distro.get_command_config(dbtype, quiet=True)
        try:
            if dbactions:
                LOG.info(("Attempting to reset your db password to %r so"
                          " that we can set it the next time you install.") % (RESET_BASE_PW))
                pwd_cmd = self.distro.get_command(dbtype, 'set_pwd')
                if pwd_cmd:
                    LOG.info("Ensuring your database is started before we operate on it.")
                    self.runtime.restart()
                    params = {
                        'OLD_PASSWORD': self.pw_gen.get_password('sql', PASSWORD_PROMPT),
                        'NEW_PASSWORD': RESET_BASE_PW,
                        'USER': self.cfg.getdefaulted("db", "sql_user", 'root'),
                        }
                    cmds = [{'cmd': pwd_cmd}]
                    utils.execute_template(*cmds, params=params)
        except IOError:
            LOG.warn(("Could not reset the database password. You might have to manually "
                      "reset the password to %r before the next install") % (RESET_BASE_PW))
            utils.log_iterable(SQL_RESET_PW_LINKS, logger=LOG,
                                header="To aid in this check out:")


class DBInstaller(comp.PkgInstallComponent):
    __meta__ = abc.ABCMeta

    def __init__(self, *args, **kargs):
        comp.PkgInstallComponent.__init__(self, *args, **kargs)
        self.runtime = DBRuntime(*args, **kargs)

    def _get_param_map(self, config_fn):
        # This dictionary will be used for parameter replacement
        # In pre-install and post-install sections
        host_ip = self.cfg.get('host', 'ip')
        out = {
            'PASSWORD': self.pw_gen.get_password("sql", PASSWORD_PROMPT),
            'BOOT_START': ("%s" % (True)).lower(),
            'USER': self.cfg.getdefaulted("db", "sql_user", 'root'),
            'SERVICE_HOST': host_ip,
            'HOST_IP': host_ip
        }
        return out

    def warm_configs(self):
        for key, prompt in WARMUP_PWS:
            self.pw_gen.get_password(key, prompt)

    @abc.abstractmethod
    def _configure_db_confs(self):
        pass

    def post_install(self):
        comp.PkgInstallComponent.post_install(self)

        # Fix up the db configs
        self._configure_db_confs()

        # Extra actions to ensure we are granted access
        dbtype = self.cfg.get("db", "type")
        dbactions = self.distro.get_command_config(dbtype, quiet=True)

        # Set your password
        try:
            if dbactions:
                pwd_cmd = self.distro.get_command(dbtype, 'set_pwd')
                if pwd_cmd:
                    LOG.info(("Attempting to set your db password"
                          " just incase it wasn't set previously."))
                    LOG.info("Ensuring your database is started before we operate on it.")
                    self.runtime.restart()
                    params = {
                        'NEW_PASSWORD': self.pw_gen.get_password("sql", PASSWORD_PROMPT),
                        'USER': self.cfg.getdefaulted("db", "sql_user", 'root'),
                        'OLD_PASSWORD': RESET_BASE_PW,
                        }
                    cmds = [{'cmd': pwd_cmd}]
                    utils.execute_template(*cmds, params=params)
        except IOError:
            LOG.warn(("Couldn't set your db password. It might have already been "
                       "set by a previous process."))

        # Ensure access granted
        if dbactions:
            grant_cmd = self.distro.get_command(dbtype, 'grant_all')
            if grant_cmd:
                user = self.cfg.getdefaulted("db", "sql_user", 'root')
                LOG.info("Updating the DB to give user %r full control of all databases." % (user))
                LOG.info("Ensuring your database is started before we operate on it.")
                self.runtime.restart()
                params = {
                    'PASSWORD': self.pw_gen.get_password("sql", PASSWORD_PROMPT),
                    'USER': user,
                }
                cmds = [{'cmd': grant_cmd}]
                utils.execute_template(*cmds, params=params)


class DBRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, *args, **kargs)
        self.wait_time = max(self.cfg.getint('default', 'service_wait_seconds'), 1)

    def _get_run_actions(self, act, exception_cls):
        dbtype = self.cfg.get("db", "type")
        distro_options = self.distro.get_command_config(dbtype)
        if distro_options is None:
            msg = BASE_ERROR % (act, dbtype)
            raise NotImplementedError(msg)
        return self.distro.get_command(dbtype, act)

    def start(self):
        if self.status() != comp.STATUS_STARTED:
            startcmd = self._get_run_actions('start', excp.StartException)
            sh.execute(*startcmd,
                run_as_root=True,
                check_exit_code=True)
            LOG.info("Please wait %s seconds while it starts up." % self.wait_time)
            sh.sleep(self.wait_time)
            return 1
        else:
            return 0

    def stop(self):
        if self.status() != comp.STATUS_STOPPED:
            stopcmd = self._get_run_actions('stop', excp.StopException)
            sh.execute(*stopcmd,
                run_as_root=True,
                check_exit_code=True)
            return 1
        else:
            return 0

    def restart(self):
        LOG.info("Restarting your database.")
        restartcmd = self._get_run_actions('restart', excp.RestartException)
        sh.execute(*restartcmd,
                    run_as_root=True,
                    check_exit_code=True)
        LOG.info("Please wait %s seconds while it restarts." % self.wait_time)
        sh.sleep(self.wait_time)
        return 1

    def status(self):
        statuscmd = self._get_run_actions('status', excp.StatusException)
        run_result = sh.execute(*statuscmd,
                            run_as_root=True,
                            check_exit_code=False)
        if not run_result:
            return comp.STATUS_UNKNOWN
        (sysout, stderr) = run_result
        combined = (str(sysout) + str(stderr)).lower()
        if combined.find("running") != -1:
            return comp.STATUS_STARTED
        elif combined.find("stop") != -1 or \
             combined.find('unrecognized') != -1:
            return comp.STATUS_STOPPED
        else:
            return comp.STATUS_UNKNOWN


def drop_db(cfg, pw_gen, distro, dbname):
    dbtype = cfg.get("db", "type")
    dropcmd = distro.get_command(dbtype, 'drop_db', silent=True)
    if dropcmd:
        params = dict()
        params['PASSWORD'] = pw_gen.get_password("sql", PASSWORD_PROMPT)
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


def create_db(cfg, pw_gen, distro, dbname):
    dbtype = cfg.get("db", "type")
    createcmd = distro.get_command(dbtype, 'create_db', silent=True)
    if createcmd:
        params = dict()
        params['PASSWORD'] = pw_gen.get_password("sql", PASSWORD_PROMPT)
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


def fetch_dbdsn(config, pw_gen, dbname=''):
    """Return the database connection string, including password."""
    user = config.get("db", "sql_user")
    host = config.get("db", "sql_host")
    port = config.get("db", "port")
    pw = pw_gen.get_password("sql", PASSWORD_PROMPT)
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
    LOG.debug("For database [%s] fetched dsn [%s]" % (dbname, dsn))
    return dsn
