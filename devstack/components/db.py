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
from devstack import settings
from devstack import shell as sh
from devstack import trace as tr
from devstack import utils

LOG = logging.getLogger("devstack.components.db")

#id
TYPE = settings.DB

#used for special setups
MYSQL = 'mysql'
DB_ACTIONS = {
    MYSQL: {
        # Of course these aren't distro independent...
        'runtime': {
            settings.UBUNTU11: {
                'start': ["service", "mysql", 'start'],
                'stop': ["service", 'mysql', "stop"],
                'status': ["service", 'mysql', "status"],
                'restart': ["service", 'mysql', "status"],
            },
            settings.RHEL6: {
                'start': ["service", "mysqld", 'start'],
                'stop': ["service", 'mysqld', "stop"],
                'status': ["service", 'mysqld', "status"],
                'restart': ["service", 'mysqld', "status"],
            },
        },
        #
        'setpwd': ['mysqladmin', '--user=%USER%', 'password', '%NEW_PASSWORD%',
                   '--password=%PASSWORD%'],
        'create_db': ['mysql', '--user=%USER%', '--password=%PASSWORD%',
                      '-e', 'CREATE DATABASE %DB%;'],
        'drop_db': ['mysql', '--user=%USER%', '--password=%PASSWORD%',
                    '-e', 'DROP DATABASE IF EXISTS %DB%;'],
        'grant_all': [
            "mysql",
            "--user=%USER%",
            "--password=%PASSWORD%",
            ("-e \"GRANT ALL PRIVILEGES ON *.* TO '%USER%'@'%' "
             "identified by '%PASSWORD%';\""),
        ],
        # we could do this in python directly, but executing allows us to
        # not have to sudo the whole program
        'host_adjust': ['perl', '-p', '-i', '-e', "'s/127.0.0.1/0.0.0.0/g'",
                        '/etc/mysql/my.cnf'],
    },
}


SQL_RESET_PW_LINKS = ['https://help.ubuntu.com/community/MysqlPasswordReset', 'http://crashmag.net/resetting-the-root-password-for-mysql-running-on-rhel-or-centos']

#used as a generic error message
BASE_ERROR = 'Currently we do not know how to %s for database type [%s]'

#used to make params for booting when started (not always take advantage of...)
BOOLEAN_OUTPUT = {True: 'true', False: 'false'}

#the pkg json files db requires for installation
REQ_PKGS = ['db.json']


class DBUninstaller(comp.PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgUninstallComponent.__init__(self, TYPE, *args, **kargs)
        self.runtime = DBRuntime(*args, **kargs)

    def pre_uninstall(self):
        dbtype = self.cfg.get("db", "type")
        dbactions = DB_ACTIONS.get(dbtype)

        try:
            self.runtime.start()
        except IOError:
            LOG.warn("Could not start your database.")

        # set pwd
        try:
            if dbactions and dbtype == MYSQL:
                LOG.info(("Attempting to reset your mysql password so"
                          " that we can set it the next time you install."))
                pwd_cmd = dbactions.get('setpwd')
                if pwd_cmd:
                    params = {
                        'PASSWORD': self.cfg.get("passwords", "sql"),
                        'USER': self.cfg.get("db", "sql_user"),
                        'NEW_PASSWORD': ''
                        }
                    cmds = [{
                            'cmd': pwd_cmd,
                            'run_as_root': True,
                            }]
                    utils.execute_template(*cmds, params=params)
        except IOError:
            LOG.warn(("Could not reset mysql password. You might have to manually "
                      "reset mysql before the next install"))
            LOG.info("To aid in this check out: %s", " or ".join(SQL_RESET_PW_LINKS))

        try:
            self.runtime.stop()
        except IOError:
            LOG.warn("Could not stop your database.")


class DBInstaller(comp.PkgInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.runtime = DBRuntime(*args, **kargs)

    def _get_param_map(self, config_fn):
        #this dictionary will be used for parameter replacement
        #in pre-install and post-install sections
        host_ip = self.cfg.get('host', 'ip')
        out = {
            'PASSWORD': self.cfg.get("passwords", "sql"),
            'BOOT_START': "%s" % BOOLEAN_OUTPUT.get(True),
            'USER': self.cfg.get("db", "sql_user"),
            'SERVICE_HOST': host_ip,
            'HOST_IP': host_ip
        }
        return out

    def _get_pkgs(self):
        pkgs = comp.PkgInstallComponent._get_pkgs(self)
        for fn in REQ_PKGS:
            full_name = sh.joinpths(settings.STACK_PKG_DIR, fn)
            pkgs = utils.extract_pkg_list([full_name], self.distro, pkgs)
        return pkgs

    def post_install(self):
        parent_result = comp.PkgInstallComponent.post_install(self)

        #extra actions to ensure we are granted access
        dbtype = self.cfg.get("db", "type")
        dbactions = DB_ACTIONS.get(dbtype)
        self.runtime.start()

        # set pwd
        try:
            if dbactions and dbtype == MYSQL:
                LOG.info(("Attempting to set your mysql password "
                          " just incase it wasn't set previously"))
                pwd_cmd = dbactions.get('setpwd')
                if pwd_cmd:
                    params = {
                        'NEW_PASSWORD': self.cfg.get("passwords", "sql"),
                        'PASSWORD': '',
                        'USER': self.cfg.get("db", "sql_user")
                        }
                    cmds = [{
                            'cmd': pwd_cmd,
                            'run_as_root': True,
                            }]
                    utils.execute_template(*cmds, params=params)
        except IOError:
            LOG.warn(("Couldn't set your password. It might have already been "
                       "set by a previous process."))

        if dbactions and dbactions.get('grant_all'):
            #update the DB to give user 'USER'@'%' full control of the all databases:
            grant_cmd = dbactions.get('grant_all')
            params = self._get_param_map(None)
            cmds = list()
            cmds.append({
                'cmd': grant_cmd,
                'run_as_root': False,
            })
            #shell seems to be needed here
            #since python escapes this to much...
            utils.execute_template(*cmds, params=params, shell=True)

        #special mysql actions
        if dbactions and dbtype == MYSQL:
            cmd = dbactions.get('host_adjust')
            if cmd:
                sh.execute(*cmd, run_as_root=True, shell=True)

        #restart it to make sure all good
        self.runtime.restart()
        return parent_result


class DBRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, TYPE, *args, **kargs)
        self.tracereader = tr.TraceReader(self.tracedir, tr.IN_TRACE)

    def _get_run_actions(self, act, exception_cls):
        pkgsinstalled = self.tracereader.packages_installed()
        if not pkgsinstalled:
            msg = "Can not %s %s since it was not installed" % (act, TYPE)
            raise exception_cls(msg)
        dbtype = self.cfg.get("db", "type")
        type_actions = DB_ACTIONS.get(dbtype)
        if type_actions is None:
            msg = BASE_ERROR % (act, dbtype)
            raise NotImplementedError(msg)
        distro_options = typeactions.get('runtime').get(self.distro)
        if distro_options is None:
            msg = BASE_ERROR % (act, dbtype)
            raise NotImplementedError(msg)
        return distro_options.get(act)

    def start(self):
        if self.status() == comp.STATUS_STOPPED:
            startcmd = self._get_run_actions('start', excp.StartException)
            sh.execute(*startcmd, run_as_root=True)
            return 1
        else:
            return 0

    def stop(self):
        if self.status() == comp.STATUS_STARTED:
            stopcmd = self._get_run_actions('stop', excp.StopException)
            sh.execute(*stopcmd, run_as_root=True)
            return 1
        else:
            return 0

    def restart(self):
        restartcmd = self._get_run_actions('restart', excp.RestartException)
        sh.execute(*restartcmd, run_as_root=True)
        return 1

    def status(self):
        statuscmd = self._get_run_actions('status', excp.StatusException)
        (sysout, _) = sh.execute(*statuscmd)
        if sysout.find("start/running") != -1:
            return comp.STATUS_STARTED
        elif sysout.find("stop/waiting") != -1:
            return comp.STATUS_STOPPED
        else:
            return comp.STATUS_UNKNOWN


def drop_db(cfg, dbname):
    dbtype = cfg.get("db", "type")
    dbactions = DB_ACTIONS.get(dbtype)
    if dbactions and dbactions.get('drop_db'):
        dropcmd = dbactions.get('drop_db')
        params = dict()
        params['PASSWORD'] = cfg.get("passwords", "sql")
        params['USER'] = cfg.get("db", "sql_user")
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


def create_db(cfg, dbname):
    dbtype = cfg.get("db", "type")
    dbactions = DB_ACTIONS.get(dbtype)
    if dbactions and dbactions.get('create_db'):
        createcmd = dbactions.get('create_db')
        params = dict()
        params['PASSWORD'] = cfg.get("passwords", "sql")
        params['USER'] = cfg.get("db", "sql_user")
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


def describe(opts=None):
    description = """
 Module: {module_name}
  Description:
   {description}
  Component options:
   {component_opts}
"""
    params = dict()
    params['component_opts'] = "TBD"
    params['module_name'] = __name__
    params['description'] = __doc__ or "Handles actions for the db component."
    out = description.format(**params)
    return out.strip("\n")
