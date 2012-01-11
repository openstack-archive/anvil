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

import Logger
import Component
from Component import (ComponentBase, RuntimeComponent,
                       UninstallComponent, InstallComponent)
import Util
from Util import (DB,
                  get_pkg_list, param_replace,
                  joinlinesep)
import Trace
from Trace import (TraceWriter, TraceReader)
import Shell
from Shell import (mkdirslist, execute, deldir)

LOG = Logger.getLogger("install.mysql")
TYPE = DB

#TODO maybe someday this should be in the pkg info?
TYPE_ACTIONS = {
    'mysql': {
        'start': ["/etc/init.d/mysql", "start"],
        'stop' : ["/etc/init.d/mysql", "stop"],
        'create_db': 'CREATE DATABASE %s;',
        'drop_db': 'DROP DATABASE IF EXISTS %s;',
        "before_install": [ 
            {
                'cmd': ["debconf-set-selections"],
                'stdin': [
                    "mysql-server-5.1 mysql-server/root_password password %PASSWORD%",
                    "mysql-server-5.1 mysql-server/root_password_again password %PASSWORD%",
                    "mysql-server-5.1 mysql-server/start_on_boot boolean %BOOT_START%",
                ],
                'run_as_root': True,
            },
        ],
        'after_install': [
            {
                'cmd': [
                    "mysql",
                    '-uroot',
                    '-p%PASSWORD%',
                    '-h127.0.0.1',
                    '-e',
                    "GRANT ALL PRIVILEGES ON *.* TO '%USER%'@'%' identified by '%PASSWORD%';",
                ],
                'stdin': [],
                'run_as_root': False,
            }
        ]
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
            am = len(pkgsfull)
            LOG.info("Removing %s packages" % (am))
            self.packager.remove_batch(pkgsfull)
        dirsmade = self.tracereader.dirs_made()
        if(len(dirsmade)):
            am = len(dirsmade)
            LOG.info("Removing %s created directories" % (am))
            for dirname in dirsmade:
                deldir(dirname)
                LOG.info("Removed %s" % (dirname))


class DBInstaller(ComponentBase, InstallComponent):
    def __init__(self, *args, **kargs):
        ComponentBase.__init__(self, TYPE, *args, **kargs)
        self.tracewriter = TraceWriter(self.tracedir, Trace.IN_TRACE)

    def download(self):
        #nothing to download, we are just a pkg
        pass

    def configure(self):
        #nothing to configure, we are just a pkg
        pass

    def _run_install_cmds(self, cmds):
        if(not cmds or len(cmds) == 0):
            return
        installparams = self._get_install_params()
        for cmdinfo in cmds:
            cmd_to_run_templ = cmdinfo.get("cmd")
            if(not cmd_to_run_templ):
                continue
            cmd_to_run = list()
            for piece in cmd_to_run_templ:
                cmd_to_run.append(param_replace(piece, installparams))
            stdin_templ = cmdinfo.get('stdin')
            stdin = None
            if(stdin_templ):
                stdin_full = list()
                for piece in stdin_templ:
                    stdin_full.append(param_replace(piece, installparams))
                stdin = joinlinesep(stdin_full)
            root_run = cmdinfo.get('run_as_root', True)
            execute(*cmd_to_run, process_input=stdin, run_as_root=root_run)

    def _get_install_params(self):
        out = dict()
        out['PASSWORD'] = self.cfg.getpw("passwords", "sql")
        out['BOOT_START'] = str(True).lower()
        out['USER'] = self.cfg.get("db", "sql_user")
        return out

    def _pre_install(self, pkgs):
        dbtype = self.cfg.get("db", "type")
        dbactions = TYPE_ACTIONS.get(dbtype)
        if(dbactions and dbactions.get("before_install")):
            LOG.info("Running pre-install commands.")
            self._run_install_cmds(dbactions.get("before_install"))

    def _post_install(self, pkgs):
        dbtype = self.cfg.get("db", "type")
        dbactions = TYPE_ACTIONS.get(dbtype)
        if(dbactions and dbactions.get("after_install")):
            LOG.info("Running post-install commands.")
            self._run_install_cmds(dbactions.get("after_install"))

    def install(self):
        #just install the pkgs
        pkgs = get_pkg_list(self.distro, TYPE)
        #run any pre-installs cmds
        self._pre_install(pkgs)
        #now install the pkgs
        pkgnames = sorted(pkgs.keys())
        LOG.debug("Installing packages %s" % (", ".join(pkgnames)))
        installparams = self._get_install_params()
        self.packager.install_batch(pkgs, installparams)
        for name in pkgnames:
            packageinfo = pkgs.get(name)
            version = packageinfo.get("version", "")
            remove = packageinfo.get("removable", True)
            # This trace is used to remove the pkgs
            self.tracewriter.package_install(name, remove, version)
        dirsmade = mkdirslist(self.tracedir)
        # This trace is used to remove the dirs created
        self.tracewriter.dir_made(*dirsmade)
        #run any post-installs cmds
        self._post_install(pkgs)
        #TODO
        # # Update the DB to give user "$MYSQL_USER"@"%" full control of the all databases:
        #sudo mysql -uroot -p$MYSQL_PASSWORD -h127.0.0.1 -e "GRANT ALL PRIVILEGES ON *.* TO '$MYSQL_USER'@'%' identified by '$MYSQL_PASSWORD';"
        #TODO
        # Edit /etc/mysql/my.cnf to change "bind-address" from localhost (127.0.0.1) to any (0.0.0.0) and stop the mysql service:
        #sudo sed -i 's/127.0.0.1/0.0.0.0/g' /etc/mysql/my.cnf
        return self.tracedir


class DBRuntime(ComponentBase, RuntimeComponent):
    def __init__(self, *args, **kargs):
        ComponentBase.__init__(self, TYPE, *args, **kargs)
        self.tracereader = TraceReader(self.tracedir, Trace.IN_TRACE)

    def start(self):
        pkgsinstalled = self.tracereader.packages_installed()
        if(len(pkgsinstalled) == 0):
            msg = "Can not start %s since it was not installed" % (TYPE)
            raise StartException(msg)
        dbtype = cfg.get("db", "type")
        typeactions = TYPE_ACTIONS.get(dbtype.lower())
        if(typeactions == None):
            msg = BASE_ERROR % ('start', dbtype)
            raise NotImplementedError(msg)
        startcmd = typeactions.get('start')
        if(startcmd):
            execute(*startcmd, run_as_root=True)
        return None

    def stop(self):
        pkgsinstalled = self.tracereader.packages_installed()
        if(len(pkgsinstalled) == 0):
            msg = "Can not stop %s since it was not installed" % (TYPE)
            raise StopException(msg)
        dbtype = cfg.get("db", "type")
        typeactions = TYPE_ACTIONS.get(dbtype.lower())
        if(typeactions == None):
            msg = BASE_ERROR % ('start', dbtype)
        stopcmd = typeactions.get('stop')
        if(stopcmd):
            execute(*stopcmd, run_as_root=True)
        return None


def drop_db(cfg, dbname):
    dbtype = cfg.get("db", "type")
    dbtypelo = dbtype.lower()
    if(dbtypelo == 'mysql'):
        #drop it
        basesql = TYPE_ACTIONS.get(dbtypelo).get('drop_db')
        sql = basesql % (dbname)
        user = cfg.get("db", "sql_user")
        pw = cfg.get("passwords", "sql")
        cmd = ['mysql', '-u' + user, '-p' + pw, '-e', sql]
        execute(*cmd)
    else:
        msg = BASE_ERROR % ('drop', dbtype)
        raise NotImplementedError(msg)


def create_db(cfg, dbname):
    dbtype = cfg.get("db", "type")
    dbtypelo = dbtype.lower()
    if(dbtypelo == 'mysql'):
        #create it
        basesql = TYPE_ACTIONS.get(dbtypelo).get('create_db')
        sql = basesql % (dbname)
        user = cfg.get("db", "sql_user")
        pw = cfg.get("passwords", "sql")
        cmd = ['mysql', '-u' + user, '-p' + pw, '-e', sql]
        execute(*cmd)
    else:
        msg = BASE_ERROR % ('create', dbtype)
        raise NotImplementedError(msg)
