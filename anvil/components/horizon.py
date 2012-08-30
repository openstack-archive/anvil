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
from anvil import components as comp
from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

import re

from anvil.components.helpers import db as dbhelper

LOG = logging.getLogger(__name__)

# Actual dir names
ROOT_HORIZON = 'horizon'
ROOT_DASH = 'openstack_dashboard'

# Name used for python install trace
HORIZON_NAME = ROOT_HORIZON
DASH_NAME = 'dashboard'

# Config files messed with
HORIZON_PY_CONF = "horizon_settings.py"
HORIZON_APACHE_CONF = 'horizon.conf'
CONFIGS = [HORIZON_PY_CONF, HORIZON_APACHE_CONF]

# DB sync that needs to happen for horizon
DB_SYNC_CMD = ['python', 'manage.py', 'syncdb', '--noinput']

# Users which apache may not like starting as..
BAD_APACHE_USERS = ['root']

# This db will be dropped and created
DB_NAME = 'horizon'


class HorizonUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)


class HorizonInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)
        self.blackhole_dir = sh.joinpths(self.get_option('app_dir'), '.blackhole')
        self.access_log =  sh.joinpths('/var/log/',
                                       self.distro.get_command_config('apache', 'name'),
                                       'horizon_access.log')
        self.error_log =  sh.joinpths('/var/log/',
                                       self.distro.get_command_config('apache', 'name'),
                                       'horizon_error.log')

    def _filter_pip_requires_line(self, line):
        # Knock off all nova, quantum, swift, keystone, cinder
        # clients since anvil will be making sure those are installed
        # instead of asking pip to do it...
        if re.search(r'([n|q|s|k|g|c]\w+client)', line, re.I):
            return None
        return line

    def verify(self):
        comp.PythonInstallComponent.verify(self)
        self._check_ug()

    @property
    def symlinks(self):
        links = super(HorizonInstaller, self).symlinks
        links[self.access_log] = [sh.joinpths(self.link_dir, 'access.log')]
        links[self.error_log] = [sh.joinpths(self.link_dir, 'error.log')]
        return links

    def _check_ug(self):
        (user, group) = self._get_apache_user_group()
        if not sh.user_exists(user):
            msg = "No user named %r exists on this system!" % (user)
            raise excp.ConfigException(msg)
        if not sh.group_exists(group):
            msg = "No group named %r exists on this system!" % (group)
            raise excp.ConfigException(msg)
        if user in BAD_APACHE_USERS:
            msg = ("You may want to adjust your configuration, "
                    "(user=%s, group=%s) will not work with apache!"
                    % (user, group))
            raise excp.ConfigException(msg)

    def target_config(self, config_name):
        if config_name == HORIZON_PY_CONF:
            # FIXME(harlowja) don't write to checked out locations...
            return sh.joinpths(self.get_option('app_dir'), ROOT_DASH, 'local', 'local_settings.py')
        else:
            return comp.PythonInstallComponent.target_config(self, config_name)

    @property
    def config_files(self):
        return list(CONFIGS)

    def _setup_blackhole(self):
        # Create an empty directory that apache uses as docroot
        self.tracewriter.dirs_made(*sh.mkdirslist(self.blackhole_dir))

    def _setup_logs(self, clear):
        log_fns = [self.access_log, self.error_log]
        utils.log_iterable(log_fns, logger=LOG,
                           header="Adjusting %s log files" % (len(log_fns)))
        for fn in log_fns:
            with sh.Rooted(True):
                if clear:
                    sh.unlink(fn, True)
                sh.mkdirslist(sh.dirname(fn))
                sh.touch_file(fn, die_if_there=False)
                sh.chmod(fn, 0666)
            self.tracewriter.file_touched(fn)
        return len(log_fns)

    def _sync_db(self):
        # Initialize the horizon database (it stores sessions and notices shown to users).
        # The user system is external (keystone).
        LOG.info("Syncing horizon to database: %s", colorizer.quote(DB_NAME))
        sh.execute(*DB_SYNC_CMD, cwd=self.get_option('app_dir'))

    def _setup_db(self):
        dbhelper.drop_db(distro=self.distro,
                         dbtype=self.get_option('db', 'type'),
                         dbname=DB_NAME,
                         **utils.merge_dicts(self.get_option('db'),
                                             dbhelper.get_shared_passwords(self)))
        dbhelper.create_db(distro=self.distro,
                           dbtype=self.get_option('db', 'type'),
                           dbname=DB_NAME,
                           **utils.merge_dicts(self.get_option('db'),
                                               dbhelper.get_shared_passwords(self)))

    def _configure_files(self):
        am = comp.PythonInstallComponent._configure_files(self)
        am += self._setup_logs(self.get_bool_option('clear-logs'))
        return am

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        if self.get_bool_option('db-sync'):
            self._setup_db()
            self._sync_db()
        if self.get_bool_option('make-blackhole'):
            self._setup_blackhole()

    def _get_apache_user_group(self):
        return (self.get_option('apache_user'), self.get_option('apache_group'))

    def config_params(self, config_fn):
        # This dict will be used to fill in the configuration
        # params with actual values
        mp = comp.PythonInstallComponent.config_params(self, config_fn)
        if config_fn == HORIZON_APACHE_CONF:
            (user, group) = self._get_apache_user_group()
            mp['GROUP'] = group
            mp['USER'] = user
            mp['HORIZON_DIR'] = self.get_option('app_dir')
            mp['HORIZON_PORT'] = self.get_int_option('port', default_value=80)
            mp['APACHE_NAME'] = self.distro.get_command_config('apache', 'name')
            mp['ERROR_LOG'] = self.error_log
            mp['ACCESS_LOG'] = self.access_log
            mp['BLACK_HOLE_DIR'] = self.blackhole_dir
        else:
            mp['OPENSTACK_HOST'] = self.get_option('ip')
            mp['DB_NAME'] = DB_NAME
            mp['DB_USER'] = self.get_option('db', 'user')
            mp['DB_PASSWORD'] = dbhelper.get_shared_passwords(self)['pw']
            mp['DB_HOST'] = self.get_option("db", "host")
            mp['DB_PORT'] = self.get_option("db", "port")
        return mp


class HorizonRuntime(comp.ProgramRuntime):
    def start(self):
        if self.status()[0].status != comp.STATUS_STARTED:
            start_cmd = self.distro.get_command('apache', 'start')
            sh.execute(*start_cmd, run_as_root=True, check_exit_code=True)
            return 1
        else:
            return 0

    def restart(self):
        restart_cmd = self.distro.get_command('apache', 'restart')
        sh.execute(*restart_cmd, run_as_root=True, check_exit_code=True)
        return 1

    def stop(self):
        if self.status()[0].status != comp.STATUS_STOPPED:
            stop_cmd = self.distro.get_command('apache', 'stop')
            sh.execute(*stop_cmd, run_as_root=True, check_exit_code=True)
            return 1
        else:
            return 0

    def status(self):
        status_cmd = self.distro.get_command('apache', 'status')
        (sysout, stderr) = sh.execute(*status_cmd, run_as_root=True, check_exit_code=False)
        combined = (sysout + stderr).lower()
        st = comp.STATUS_UNKNOWN
        if combined.find("is running") != -1:
            st = comp.STATUS_STARTED
        elif utils.has_any(combined, 'stopped', 'unrecognized', 'not running'):
            st = comp.STATUS_STOPPED
        return [
            comp.ProgramStatus(status=st,
                               details=(sysout + stderr).strip()),
        ]
