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

import os

from devstack import component as comp
from devstack import exceptions as excp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

#id
TYPE = settings.HORIZON

#actual dir names
ROOT_HORIZON = 'horizon'
HORIZON_NAME = 'horizon'
ROOT_DASH = 'openstack-dashboard'
DASH_NAME = 'dashboard'

#config files messed with
HORIZON_PY_CONF = "horizon_settings.py"
HORIZON_PY_CONF_TGT = ['local', 'local_settings.py']
HORIZON_APACHE_CONF = '000-default'
HORIZON_APACHE_TGT = ['/', 'etc', 'apache2', 'sites-enabled', '000-default']
CONFIGS = [HORIZON_PY_CONF, HORIZON_APACHE_CONF]

#db sync that needs to happen for horizon
DB_SYNC_CMD = ['python', 'manage.py', 'syncdb']

#special apache directory (TODO describe more about this)
BLACKHOLE_DIR = '.blackhole'

#hopefully this will be distro independent ??
APACHE_RESTART_CMD = ['service', 'apache2', 'restart']
APACHE_START_CMD = ['service', 'apache2', 'start']
APACHE_STOP_CMD = ['service', 'apache2', 'stop']
APACHE_STATUS_CMD = ['service', 'apache2', 'status']

#users which apache may not like starting as
BAD_APACHE_USERS = ['root']

LOG = logging.getLogger("devstack.components.horizon")

#the pkg json files horizon requires for installation
REQ_PKGS = ['general.json', 'horizon.json']

#pip files that horizon requires
REQ_PIPS = ['general.json', 'horizon.json']


class HorizonUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)


class HorizonInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.horizon_dir = sh.joinpths(self.appdir, ROOT_HORIZON)
        self.dash_dir = sh.joinpths(self.appdir, ROOT_DASH)
        self._check_ug()

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "horizon_repo"),
            'branch': ("git", "horizon_branch"),
        })
        return places

    def _get_symlinks(self):
        src = self._get_target_config_name(HORIZON_APACHE_CONF)
        tgt = sh.joinpths(*HORIZON_APACHE_TGT)
        links = dict()
        links[src] = tgt
        return links

    def _check_ug(self):
        (user, group) = self._get_apache_user_group()
        if not sh.user_exists(user):
            msg = "No user named %s exists on this system!" % (user)
            raise excp.ConfigException(msg)
        if not sh.group_exists(group):
            msg = "No group named %s exists on this system!" % (group)
            raise excp.ConfigException(msg)

    def _get_pkgs(self):
        return list(REQ_PKGS)

    def _get_pips(self):
        return list(REQ_PIPS)

    def _get_target_config_name(self, config_name):
        if config_name == HORIZON_PY_CONF:
            return sh.joinpths(self.dash_dir, *HORIZON_PY_CONF_TGT)
        else:
            return comp.PythonInstallComponent._get_target_config_name(self, config_name)

    def _get_python_directories(self):
        py_dirs = dict()
        py_dirs[HORIZON_NAME] = self.horizon_dir
        py_dirs[DASH_NAME] = self.dash_dir
        return py_dirs

    def _get_config_files(self):
        return list(CONFIGS)

    def _setup_blackhole(self):
        #create an empty directory that apache uses as docroot
        black_dir = sh.joinpths(self.appdir, BLACKHOLE_DIR)
        self.tracewriter.make_dir(black_dir)

    def _sync_db(self):
        #Initialize the horizon database (it stores sessions and notices shown to users).
        #The user system is external (keystone).
        LOG.info("Initializing the horizon database.")
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
        comp.PythonInstallComponent.post_install(self)
        self._fake_quantum()
        self._sync_db()
        self._setup_blackhole()
        self._ensure_db_access()

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
                LOG.warn("You may want to adjust your configuration, (user=%s, group=%s) will typically not work with apache!", user, group)
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
    params['description'] = __doc__ or "Handles actions for the horizon component."
    out = description.format(**params)
    return out.strip("\n")
