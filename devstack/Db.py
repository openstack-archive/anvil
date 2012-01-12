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
import Component
from Component import (ComponentBase, RuntimeComponent,
                       UninstallComponent, InstallComponent)
import Util
from Util import (DB,
                  get_pkg_list,
                  execute_template)
import Exceptions
from Exceptions import StartException, StopException, StatusException
import Trace
from Trace import (TraceWriter, TraceReader)
import Shell
from Shell import (mkdirslist, execute, deldir,
                  load_file, write_file)

LOG = Logger.getLogger("install.db")
TYPE = DB
MYSQL = 'mysql'
DB_ACTIONS = {
    MYSQL: {
        #hopefully these are distro independent, these should be since they are invoking system init scripts
        'start': ["service", "mysql", 'start'],
        'stop': ["service", 'mysql', "stop"],
        'status': ["service", 'mysql', "status"],
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
        'host_adjust':  ['perl', '-p', '-i', '-e'] + ["'s/127.0.0.1/0.0.0.0/g'", '/etc/mysql/my.cnf'],
    },
}

BASE_ERROR = 'Currently we do not know how to %s for database type [%s]'


class DBUninstaller(ComponentBase, UninstallComponent):
    def __init__(self, *args, **kargs):
        ComponentBase.__init__(self, TYPE, *args, **kargs)
        self.tracereader = TraceReader(self.tracedir, Trace.IN_TRACE)

    def unconfigure(self):
        #nothing to unconfigure, we are just a pkg
        pass

    def uninstall(self):
        #clean out removeable packages
        pkgsfull = self.tracereader.packages_installed()
        if(len(pkgsfull)):
            LOG.info("Removing %s packages" % (len(pkgsfull)))
            self.packager.remove_batch(pkgsfull)
        dirsmade = self.tracereader.dirs_made()
        if(len(dirsmade)):
            LOG.info("Removing %s created directories" % (len(dirsmade)))
            for dirname in dirsmade:
                deldir(dirname)
                LOG.info("Removed %s" % (dirname))


class DBInstaller(ComponentBase, InstallComponent):
    def __init__(self, *args, **kargs):
        ComponentBase.__init__(self, TYPE, *args, **kargs)
        self.tracewriter = TraceWriter(self.tracedir, Trace.IN_TRACE)
        self.runtime = DBRuntime(*args, **kargs)

    def download(self):
        #nothing to download, we are just a pkg
        pass

    def configure(self):
        #nothing to configure, we are just a pkg
        pass

    def _get_install_params(self):
        #this dictionary will be used for parameter replacement
        #in pre-install and post-install sections
        out = dict()
        out['PASSWORD'] = self.cfg.getpw("passwords", "sql")
        out['BOOT_START'] = str(True).lower()
        out['USER'] = self.cfg.get("db", "sql_user")
        return out

    def _post_install(self, pkgs):
        #run whatever the pkgs have specified
        Packager.post_install(pkgs, self._get_install_params())
        #extra actions to ensure we are granted access
        dbtype = self.cfg.get("db", "type")
        dbactions = DB_ACTIONS.get(dbtype)
        if(dbactions and dbactions.get('grant_all')):
            #update the DB to give user 'USER'@'%' full control of the all databases:
            grant_cmd = dbactions.get('grant_all')
            params = self._get_install_params()
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

    def _pre_install(self, pkgs):
        #run whatever the pkgs have specified
        Packager.pre_install(pkgs, self._get_install_params())

    def install(self):
        #just install the pkgs
        pkgs = get_pkg_list(self.distro, TYPE)
        pkgnames = sorted(pkgs.keys())
        LOG.info("Installing packages %s" % (", ".join(pkgnames)))
        #run any pre-installs cmds
        self._pre_install(pkgs)
        #now install the pkgs
        self.packager.install_batch(pkgs)
        #add trace used to remove the pkgs
        for name in pkgnames:
            self.tracewriter.package_install(name, pkgs.get(name))
        #run any post-installs cmds
        self._post_install(pkgs)
        #it should be started now, if not start it
        self.runtime.start()
        return self.tracedir


class DBRuntime(ComponentBase, RuntimeComponent):
    def __init__(self, *args, **kargs):
        ComponentBase.__init__(self, TYPE, *args, **kargs)
        self.tracereader = TraceReader(self.tracedir, Trace.IN_TRACE)

    def start(self):
        #ensure it was actually installed
        pkgsinstalled = self.tracereader.packages_installed()
        if(len(pkgsinstalled) == 0):
            msg = "Can not start %s since it was not installed" % (TYPE)
            raise StartException(msg)
        #figure out how to start it
        dbtype = self.cfg.get("db", "type")
        typeactions = DB_ACTIONS.get(dbtype)
        if(typeactions == None or not typeactions.get('start')):
            msg = BASE_ERROR % ('start', dbtype)
            raise NotImplementedError(msg)
        #check if already going
        if(self.status().find('start') == -1):
            #run whatever the command is to get it going
            startcmd = typeactions.get('start')
            execute(*startcmd, run_as_root=True)
        return None

    def stop(self):
        #make sure it was actually installed
        pkgsinstalled = self.tracereader.packages_installed()
        if(len(pkgsinstalled) == 0):
            msg = "Can not stop %s since it was not installed" % (TYPE)
            raise StopException(msg)
        #figure out how to stop it
        dbtype = self.cfg.get("db", "type")
        typeactions = DB_ACTIONS.get(dbtype)
        if(typeactions == None or not typeactions.get('stop')):
            msg = BASE_ERROR % ('stop', dbtype)
            raise NotImplementedError(msg)
        #check if already stopped
        if(self.status().find('stop') == -1):
            #run whatever the command is to get it stopped
            stopcmd = typeactions.get('stop')
            execute(*stopcmd, run_as_root=True)
        return None

    def status(self):
        #make sure it was actually installed
        pkgsinstalled = self.tracereader.packages_installed()
        if(len(pkgsinstalled) == 0):
            msg = "Can not check the status of %s since it was not installed" % (TYPE)
            raise StatusException(msg)
        #figure out how to get the status of it
        dbtype = self.cfg.get("db", "type")
        if(typeactions == None or not typeactions.get('status')):
            msg = BASE_ERROR % ('status', dbtype)
            raise NotImplementedError(msg)
        statuscmd = typeactions.get('status')
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
