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
from anvil import component as comp
from anvil import constants
from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.helpers import db as dbhelper

import abc

LOG = logging.getLogger(__name__)

# Need to reset pw to blank since this distributions don't seem to
# always reset it when u uninstall the db
RESET_BASE_PW = ''

# Links about how to reset if we fail to set the PW
SQL_RESET_PW_LINKS = [
    'https://help.ubuntu.com/community/MysqlPasswordReset',
    'http://dev.mysql.com/doc/refman/5.0/en/resetting-permissions.html',
]

# Copies from helper
BASE_ERROR = dbhelper.BASE_ERROR

# PW keys we warm up so u won't be prompted later
PASSWORD_PROMPT = dbhelper.PASSWORD_PROMPT
WARMUP_PWS = [('sql', PASSWORD_PROMPT)]


class DBUninstaller(comp.PkgUninstallComponent):

    def __init__(self, *args, **kargs):
        comp.PkgUninstallComponent.__init__(self, *args, **kargs)
        runtime_cls = self.siblings.get('running')
        if not runtime_cls:
            self.runtime = DBRuntime(*args, **kargs)
        else:
            self.runtime = runtime_cls(*args, **kargs)

    def warm_configs(self):
        for key, prompt in WARMUP_PWS:
            self.cfg.get_password(key, prompt)

    def pre_uninstall(self):
        dbtype = self.cfg.get("db", "type")
        dbactions = self.distro.get_command_config(dbtype, quiet=True)
        try:
            if dbactions:
                LOG.info(("Attempting to reset your db password to %s so"
                          " that we can set it the next time you install."), colorizer.quote(RESET_BASE_PW))
                pwd_cmd = self.distro.get_command(dbtype, 'set_pwd')
                if pwd_cmd:
                    LOG.info("Ensuring your database is started before we operate on it.")
                    self.runtime.restart()
                    params = {
                        'OLD_PASSWORD': self.cfg.get_password('sql', PASSWORD_PROMPT),
                        'NEW_PASSWORD': RESET_BASE_PW,
                        'USER': self.cfg.getdefaulted("db", "sql_user", 'root'),
                        }
                    cmds = [{'cmd': pwd_cmd}]
                    utils.execute_template(*cmds, params=params)
        except IOError:
            LOG.warn(("Could not reset the database password. You might have to manually "
                      "reset the password to %s before the next install"), colorizer.quote(RESET_BASE_PW))
            utils.log_iterable(SQL_RESET_PW_LINKS, logger=LOG,
                                header="To aid in this check out:")


class DBInstaller(comp.PkgInstallComponent):
    __meta__ = abc.ABCMeta

    def __init__(self, *args, **kargs):
        comp.PkgInstallComponent.__init__(self, *args, **kargs)
        runtime_cls = self.siblings.get('running')
        if not runtime_cls:
            self.runtime = DBRuntime(*args, **kargs)
        else:
            self.runtime = runtime_cls(*args, **kargs)

    def _get_param_map(self, config_fn):
        # This dictionary will be used for parameter replacement
        # In pre-install and post-install sections
        mp = comp.PkgInstallComponent._get_param_map(self, config_fn)
        adds = {
            'PASSWORD': self.cfg.get_password("sql", PASSWORD_PROMPT),
            'BOOT_START': ("%s" % (True)).lower(),
            'USER': self.cfg.getdefaulted("db", "sql_user", 'root'),
            'SERVICE_HOST': self.cfg.get('host', 'ip'),
            'HOST_IP': self.cfg.get('host', 'ip'),
        }
        mp.update(adds)
        return mp

    def warm_configs(self):
        for key, prompt in WARMUP_PWS:
            self.cfg.get_password(key, prompt)

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
                        'NEW_PASSWORD': self.cfg.get_password("sql", PASSWORD_PROMPT),
                        'USER': self.cfg.getdefaulted("db", "sql_user", 'root'),
                        'OLD_PASSWORD': RESET_BASE_PW,
                        }
                    cmds = [{'cmd': pwd_cmd}]
                    utils.execute_template(*cmds, params=params)
        except IOError:
            LOG.warn(("Couldn't set your db password. It might have already been "
                       "set by a previous process."))

        # Ensure access granted
        user = self.cfg.getdefaulted("db", "sql_user", 'root')
        dbhelper.grant_permissions(self.cfg, self.distro, user, restart_func=self.runtime.restart)


class DBRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, *args, **kargs)
        self.wait_time = max(self.cfg.getint('DEFAULT', 'service_wait_seconds'), 1)

    def _get_run_actions(self, act, exception_cls):
        dbtype = self.cfg.get("db", "type")
        distro_options = self.distro.get_command_config(dbtype)
        if distro_options is None:
            raise NotImplementedError(BASE_ERROR % (act, dbtype))
        return self.distro.get_command(dbtype, act)

    def start(self):
        if self._status() != constants.STATUS_STARTED:
            startcmd = self._get_run_actions('start', excp.StartException)
            sh.execute(*startcmd, run_as_root=True, check_exit_code=True)
            LOG.info("Please wait %s seconds while it starts up." % self.wait_time)
            sh.sleep(self.wait_time)
            return 1
        else:
            return 0

    def stop(self):
        if self._status() != constants.STATUS_STOPPED:
            stopcmd = self._get_run_actions('stop', excp.StopException)
            sh.execute(*stopcmd, run_as_root=True, check_exit_code=True)
            return 1
        else:
            return 0

    def restart(self):
        LOG.info("Restarting your database.")
        restartcmd = self._get_run_actions('restart', excp.RestartException)
        sh.execute(*restartcmd, run_as_root=True, check_exit_code=True)
        LOG.info("Please wait %s seconds while it restarts." % self.wait_time)
        sh.sleep(self.wait_time)
        return 1

    def _status(self):
        statuscmd = self._get_run_actions('status', excp.StatusException)
        (sysout, stderr) = sh.execute(*statuscmd, run_as_root=True, check_exit_code=False)
        combined = (str(sysout) + str(stderr)).lower()
        if combined.find("running") != -1:
            return constants.STATUS_STARTED
        elif combined.find("stop") != -1 or \
             combined.find('unrecognized') != -1:
            return constants.STATUS_STOPPED
        else:
            return constants.STATUS_UNKNOWN
