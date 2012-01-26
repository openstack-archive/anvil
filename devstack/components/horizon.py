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

from devstack import component as comp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh

#id
TYPE = settings.HORIZON

ROOT_HORIZON = 'horizon'
HORIZON_NAME = 'horizon'
ROOT_DASH = 'openstack-dashboard'
DASH_NAME = 'dashboard'

HORIZON_PY_CONF = "horizon_settings.py"
HORIZON_PY_CONF_TGT = ['local', 'local_settings.py']
HORIZON_APACHE_CONF = '000-default'
HORIZON_APACHE_TGT = ['/', 'etc', 'apache2', 'sites-enabled', '000-default']

CONFIGS = [HORIZON_PY_CONF, HORIZON_APACHE_CONF]
DB_SYNC_CMD = ['python', 'manage.py', 'syncdb']
BLACKHOLE_DIR = '.blackhole'

#hopefully this will be distro independent ??
APACHE_RESTART_CMD = ['service', 'apache2', 'restart']
APACHE_START_CMD = ['service', 'apache2', 'start']
APACHE_STOP_CMD = ['service', 'apache2', 'stop']
APACHE_STATUS_CMD = ['service', 'apache2', 'status']

#users which apache may not like starting as
BAD_APACHE_USERS = ['root']

LOG = logging.getLogger("devstack.components.horizon")


class HorizonUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)


class HorizonInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.git_loc = self.cfg.get("git", "horizon_repo")
        self.git_branch = self.cfg.get("git", "horizon_branch")
        self.horizon_dir = sh.joinpths(self.appdir, ROOT_HORIZON)
        self.dash_dir = sh.joinpths(self.appdir, ROOT_DASH)

    def _get_download_locations(self):
        places = comp.PythonInstallComponent._get_download_locations(self)
        places.append({
            'uri': self.git_loc,
            'branch': self.git_branch,
        })
        return places

    def _get_target_config_name(self, config_name):
        if config_name == HORIZON_PY_CONF:
            return sh.joinpths(self.dash_dir, *HORIZON_PY_CONF_TGT)
        elif config_name == HORIZON_APACHE_CONF:
            #this may require sudo of the whole program to be able to write here.
            return sh.joinpths(*HORIZON_APACHE_TGT)
        else:
            return comp.PythonInstallComponent._get_target_config_name(self, config_name)

    def _get_python_directories(self):
        py_dirs = list()
        py_dirs.append({
            'name': HORIZON_NAME,
            'work_dir': self.horizon_dir,
        })
        py_dirs.append({
            'name': DASH_NAME,
            'work_dir': self.dash_dir,
        })
        return py_dirs

    def _get_config_files(self):
        #these are the config files we will be adjusting
        return list(CONFIGS)

    def _setup_blackhole(self):
        #create an empty directory that apache uses as docroot
        black_dir = sh.joinpths(self.appdir, BLACKHOLE_DIR)
        self.tracewriter.make_dir(black_dir)
        return black_dir

    def _sync_db(self):
        #Initialize the horizon database (it stores sessions and notices shown to users).
        #The user system is external (keystone).
        sh.execute(*DB_SYNC_CMD, cwd=self.dash_dir)

    def _fake_quantum(self):
        #Horizon currently imports quantum even if you aren't using it.
        #Instead of installing quantum we can create a simple module
        #that will pass the initial imports.
        if settings.QUANTUM in self.instances:
            return
        else:
            #Make the fake quantum
            quantum_dir = sh.joinpths(self.dash_dir, 'quantum')
            self.tracewriter.make_dir(quantum_dir)
            self.tracewriter.touch_file(sh.joinpths(quantum_dir, '__init__.py'))
            self.tracewriter.touch_file(sh.joinpths(quantum_dir, 'client.py'))

    def _ensure_db_access(self):
        # ../openstack-dashboard/local needs to be writeable by the runtime user
        # since currently its storing the sql-lite databases there (TODO fix that)
        path = sh.joinpths(self.dash_dir, 'local')
        if sh.isdir(path):
            (user, group) = self._get_apache_user_group()
            LOG.info("Changing ownership (recursively) of %s so that it can be used by %s - %s",
                path, user, group)
            uid = sh.getuid(user)
            gid = sh.getgid(group)
            sh.chown_r(path, uid, gid)

    def post_install(self):
        parent_result = comp.PythonInstallComponent.post_install(self)
        self._fake_quantum()
        self._sync_db()
        self._setup_blackhole()
        self._ensure_db_access()
        return parent_result

    def _get_apache_user_group(self):
        user = self.cfg.get('horizon', 'apache_user')
        if not user:
            user = sh.getuser()
        group = self.cfg.get('horizon', 'apache_group')
        if not group:
            group = sh.getgroupname()
        return (user, group)

    def _get_param_map(self, config_fn):
        #this dict will be used to fill in the configuration
        #params with actual values
        mp = dict()
        if config_fn == HORIZON_APACHE_CONF:
            (user, group) = self._get_apache_user_group()
            if user in BAD_APACHE_USERS:
                LOG.warn("You may want to adjust your configuration, user=%s,group=%s will typically not work with apache", user, group)
            mp['USER'] = user
            mp['GROUP'] = group
            mp['HORIZON_DIR'] = self.appdir
            mp['HORIZON_PORT'] = self.cfg.get('horizon', 'port')
        else:
            #Enable quantum in dashboard, if requested
            mp['QUANTUM_ENABLED'] = "%s" % (settings.QUANTUM in self.instances)
            mp['OPENSTACK_HOST'] = self.cfg.get('host', 'ip')
        return mp


class HorizonRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, TYPE, *args, **kargs)

    def start(self):
        curr_status = self.status()
        if curr_status == comp.STATUS_STARTED:
            #restart it ?
            return self.restart()
        else:
            sh.execute(*APACHE_START_CMD,
                run_as_root=True)
            return 1

    def restart(self):
        curr_status = self.status()
        if curr_status == comp.STATUS_STARTED:
            sh.execute(*APACHE_RESTART_CMD,
                run_as_root=True)
            return 1
        return 0

    def stop(self):
        curr_status = self.status()
        if curr_status == comp.STATUS_STARTED:
            sh.execute(*APACHE_STOP_CMD,
                run_as_root=True)
            return 1
        return 0

    def status(self):
        (sysout, _) = sh.execute(*APACHE_STATUS_CMD,
                            check_exit_code=False)
        if sysout.find("is running") != -1:
            return comp.STATUS_STARTED
        elif sysout.find("NOT running") != -1:
            return comp.STATUS_STOPPED
        else:
            return comp.STATUS_UNKNOWN
