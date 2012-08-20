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
HORIZON_PY_CONF_TGT = ['local', 'local_settings.py']
HORIZON_APACHE_CONF = '000-default'
CONFIGS = [HORIZON_PY_CONF, HORIZON_APACHE_CONF]

# DB sync that needs to happen for horizon
DB_SYNC_CMD = ['python', 'manage.py', 'syncdb', '--noinput']

# Special apache directory (TODO describe more about this)
BLACKHOLE_DIR = '.blackhole'

# Other apache settings
APACHE_ERROR_LOG_FN = "error.log"
APACHE_ACCESS_LOG_FN = "access.log"
APACHE_DEF_PORT = 80

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
        self.log_dir = sh.joinpths(self.get_option('component_dir'), 'logs')

    def _filter_pip_requires_line(self, line):
        if line.lower().find('novaclient') != -1:
            return None
        if line.lower().find('quantumclient') != -1:
            return None
        if line.lower().find('swiftclient') != -1:
            return None
        if line.lower().find('keystoneclient') != -1:
            return None
        if line.lower().find('glanceclient') != -1:
            return None
        if line.lower().find('cinderclient') != -1:
            return None
        return line

    def verify(self):
        comp.PythonInstallComponent.verify(self)
        self._check_ug()

    @property
    def symlinks(self):
        links = super(HorizonInstaller, self).symlinks
        link_tgt = self.distro.get_command_config('apache', 'settings', 'conf-link-target', quiet=True)
        if link_tgt:
            src = self.target_config(HORIZON_APACHE_CONF)
            links[src] = link_tgt
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
            # FIXME don't write to checked out locations...
            dash_dir = sh.joinpths(self.get_option('app_dir'), ROOT_DASH)
            return sh.joinpths(dash_dir, *HORIZON_PY_CONF_TGT)
        else:
            return comp.PythonInstallComponent.target_config(self, config_name)

    @property
    def config_files(self):
        return list(CONFIGS)

    def _setup_blackhole(self):
        # Create an empty directory that apache uses as docroot
        black_hole_dir = sh.joinpths(self.get_option('app_dir'), BLACKHOLE_DIR)
        self.tracewriter.dirs_made(*sh.mkdirslist(black_hole_dir))

    def _sync_db(self):
        # Initialize the horizon database (it stores sessions and notices shown to users).
        # The user system is external (keystone).
        LOG.info("Syncing horizon to database: %s", colorizer.quote(DB_NAME))
        sh.execute(*DB_SYNC_CMD, cwd=self.get_option('app_dir'))

    def _setup_db(self):
        dbhelper.drop_db(distro=self.distro,
                         dbtype=self.get_option('db.type'),
                         dbname=DB_NAME,
                         **utils.merge_dicts(self.get_option('db'),
                                             dbhelper.get_shared_passwords(self)))
        dbhelper.create_db(distro=self.distro,
                           dbtype=self.get_option('db.type'),
                           dbname=DB_NAME,
                           **utils.merge_dicts(self.get_option('db'),
                                               dbhelper.get_shared_passwords(self)))

    def pre_install(self):
        comp.PythonInstallComponent.pre_install(self)
        self.tracewriter.dirs_made(*sh.mkdirslist(self.log_dir))

    def _config_fixups(self):
        pass

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        if self.get_option('db-sync'):
            self._setup_db()
            self._sync_db()
        if self.get_option('make-blackhole'):
            self._setup_blackhole()
        self._config_fixups()

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
            mp['ACCESS_LOG'] = sh.joinpths(self.log_dir, APACHE_ACCESS_LOG_FN)
            mp['ERROR_LOG'] = sh.joinpths(self.log_dir, APACHE_ERROR_LOG_FN)
            mp['HORIZON_DIR'] = self.get_option('app_dir')
            mp['HORIZON_PORT'] = self.get_option('port', APACHE_DEF_PORT)
            mp['VPN_DIR'] = sh.joinpths(self.get_option('app_dir'), "vpn")
        else:
            mp['OPENSTACK_HOST'] = self.get_option('ip')
            mp['DB_NAME'] = DB_NAME
            mp['DB_USER'] = self.get_option('db.user')
            mp['DB_PASSWORD'] = dbhelper.get_shared_passwords(self)
            mp['DB_HOST'] = self.get_option("db.host")
            mp['DB_PORT'] = self.get_option("db.port")
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
        elif combined.find("not running") != -1 or \
             combined.find("stopped") != -1 or \
             combined.find('unrecognized') != -1:
            st = comp.STATUS_STOPPED
        return [
            comp.ProgramStatus(status=st,
                               details=(sysout + stderr).strip()),
        ]
