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

import re

import Logger
import Packager

#TODO fix these
from Component import (PkgUninstallComponent, PkgInstallComponent,
                        ComponentBase, RuntimeComponent)
from Util import (DB,
                  get_host_ip,
                  execute_template)
from Exceptions import (StartException, StopException,
                    StatusException, RestartException)
from Shell import (execute)
from Trace import (TraceReader,
                    IN_TRACE)

LOG = Logger.getLogger("install.db")
TYPE = DB
MYSQL = 'mysql'
DB_ACTIONS = {
    MYSQL: {
        #hopefully these are distro independent, these should be since they are invoking system init scripts
        'start': ["service", "mysql", 'start'],
        'stop': ["service", 'mysql', "stop"],
        'status': ["service", 'mysql', "status"],
        'restart': ["service", 'mysql', "status"],
        #
        'create_db': ['mysql', '--user=%USER%', '--password=%PASSWORD%', '-e', 'CREATE DATABASE %DB%;'],
        'drop_db': ['mysql', '--user=%USER%', '--password=%PASSWORD%', '-e', 'DROP DATABASE IF EXISTS %DB%;'],
        'grant_all': [
            "mysql",
            "--user=%USER%",
            "--password=%PASSWORD%",
            "-e \"GRANT ALL PRIVILEGES ON *.* TO '%USER%'@'%' identified by '%PASSWORD%';\"",
        ],
        #we could do this in python directly, but executing allows us to not have to sudo the whole program
        'host_adjust': ['perl', '-p', '-i', '-e'] + ["'s/127.0.0.1/0.0.0.0/g'", '/etc/mysql/my.cnf'],
    },
}

BASE_ERROR = 'Currently we do not know how to %s for database type [%s]'


class DBUninstaller(PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        PkgUninstallComponent.__init__(self, TYPE, *args, **kargs)


class DBInstaller(PkgInstallComponent):
    def __init__(self, *args, **kargs):
        PkgInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.runtime = DBRuntime(*args, **kargs)

    def _get_download_location(self):
        return (None, None)

    def _get_param_map(self, fn=None):
        #this dictionary will be used for parameter replacement
        #in pre-install and post-install sections
        out = dict()
        out['PASSWORD'] = self.cfg.getpw("passwords", "sql")
        out['BOOT_START'] = str(True).lower()
        out['USER'] = self.cfg.get("db", "sql_user")
        hostip = get_host_ip(self.cfg)
        out['SERVICE_HOST'] = hostip
        out['HOST_IP'] = hostip
        return out

    def install(self):
        pres = PkgInstallComponent.install(self)
        #extra actions to ensure we are granted access
        dbtype = self.cfg.get("db", "type")
        dbactions = DB_ACTIONS.get(dbtype)
        if(dbactions and dbactions.get('grant_all')):
            #update the DB to give user 'USER'@'%' full control of the all databases:
            grant_cmd = dbactions.get('grant_all')
            params = self._get_param_map()
            cmds = list()
            cmds.append({
                'cmd': grant_cmd,
                'run_as_root': False,
            })
            #shell seems to be needed here
            #since python escapes this to much...
            execute_template(*cmds, params=params, shell=True)
        #special mysql actions
        if(dbactions and dbtype == MYSQL):
            cmd = dbactions.get('host_adjust')
            if(cmd):
                execute(*cmd, run_as_root=True, shell=True)
        #restart it to make sure all good
        self.runtime.restart()
        return pres


class DBRuntime(ComponentBase, RuntimeComponent):
    def __init__(self, *args, **kargs):
        ComponentBase.__init__(self, TYPE, *args, **kargs)
        self.tracereader = TraceReader(self.tracedir, IN_TRACE)

    def _gettypeactions(self, act, exception_cls):
        pkgsinstalled = self.tracereader.packages_installed()
        if(len(pkgsinstalled) == 0):
            msg = "Can not %s %s since it was not installed" % (act, TYPE)
            raise exception_cls(msg)
        #figure out how to do it
        dbtype = self.cfg.get("db", "type")
        typeactions = DB_ACTIONS.get(dbtype)
        if(typeactions == None or not typeactions.get(act)):
            msg = BASE_ERROR % (act, dbtype)
            raise NotImplementedError(msg)
        return typeactions.get(act)

    def start(self):
        if(self.status().find('start') == -1):
            startcmd = self._gettypeactions('start', StartException)
            execute(*startcmd, run_as_root=True)
        return None

    def stop(self):
        if(self.status().find('stop') == -1):
            stopcmd = self._gettypeactions('stop', StopException)
            execute(*stopcmd, run_as_root=True)
        return None

    def restart(self):
        restartcmd = self._gettypeactions('restart', RestartException)
        execute(*restartcmd, run_as_root=True)
        return None

    def status(self):
        statuscmd = self._gettypeactions('status', StatusException)
        (sysout, stderr) = execute(*statuscmd, run_as_root=True)
        return sysout.strip()


def drop_db(cfg, dbname):
    dbtype = cfg.get("db", "type")
    dbactions = DB_ACTIONS.get(dbtype)
    if(dbactions and dbactions.get('drop_db')):
        dropcmd = dbactions.get('drop_db')
        params = dict()
        params['PASSWORD'] = cfg.getpw("passwords", "sql")
        params['USER'] = cfg.get("db", "sql_user")
        params['DB'] = dbname
        cmds = list()
        cmds.append({
            'cmd': dropcmd,
            'run_as_root': False,
        })
        execute_template(*cmds, params=params)
    else:
        msg = BASE_ERROR % ('drop', dbtype)
        raise NotImplementedError(msg)


def create_db(cfg, dbname):
    dbtype = cfg.get("db", "type")
    dbactions = DB_ACTIONS.get(dbtype)
    if(dbactions and dbactions.get('create_db')):
        createcmd = dbactions.get('create_db')
        params = dict()
        params['PASSWORD'] = cfg.getpw("passwords", "sql")
        params['USER'] = cfg.get("db", "sql_user")
        params['DB'] = dbname
        cmds = list()
        cmds.append({
            'cmd': createcmd,
            'run_as_root': False,
        })
        execute_template(*cmds, params=params)
    else:
        msg = BASE_ERROR % ('create', dbtype)
        raise NotImplementedError(msg)
