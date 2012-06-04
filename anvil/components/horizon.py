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

from anvil.helpers import db as dbhelper

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
DB_SYNC_CMD = ['python', 'manage.py', 'syncdb']

# Special apache directory (TODO describe more about this)
BLACKHOLE_DIR = '.blackhole'

# Other apache settings
APACHE_ERROR_LOG_FN = "error.log"
APACHE_ACCESS_LOG_FN = "access.log"
APACHE_DEF_PORT = 80

# Users which apache may not like starting as..
BAD_APACHE_USERS = ['root']

# Apache logs will go here
LOGS_DIR = "logs"

# This db will be dropped and created
DB_NAME = 'horizon'


class HorizonUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)


class HorizonInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)
        self.log_dir = sh.joinpths(self.get_option('component_dir'), LOGS_DIR)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "horizon_repo"),
            'branch': ("git", "horizon_branch"),
        })
        return places

    def verify(self):
        comp.PythonInstallComponent.verify(self)
        self._check_ug()

    def _get_symlinks(self):
        links = comp.PythonInstallComponent._get_symlinks(self)
        link_tgt = self.distro.get_command_config(
            'apache', 'settings', 'conf-link-target',
            quiet=True)
        if link_tgt:
            src = self._get_target_config_name(HORIZON_APACHE_CONF)
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

    def _get_target_config_name(self, config_name):
        if config_name == HORIZON_PY_CONF:
            # FIXME don't write to checked out locations...
            dash_dir = sh.joinpths(self.get_option('app_dir'), ROOT_DASH)
            return sh.joinpths(dash_dir, *HORIZON_PY_CONF_TGT)
        else:
            return comp.PythonInstallComponent._get_target_config_name(self, config_name)

    def _get_config_files(self):
        return list(CONFIGS)

    def _setup_blackhole(self):
        # Create an empty directory that apache uses as docroot
        self.tracewriter.dirs_made(*sh.mkdirslist(sh.joinpths(self.get_option('app_dir'), BLACKHOLE_DIR)))

    def _sync_db(self):
        # Initialize the horizon database (it stores sessions and notices shown to users).
        # The user system is external (keystone).
        LOG.info("Syncing horizon to database: %s", colorizer.quote(DB_NAME))
        sh.execute(*DB_SYNC_CMD, cwd=self.get_option('app_dir'))

    def _setup_db(self):
        dbhelper.drop_db(self.cfg, self.distro, DB_NAME)
        dbhelper.create_db(self.cfg, self.distro, DB_NAME, utf8=True)

    def pre_install(self):
        comp.PythonInstallComponent.pre_install(self)
        self.tracewriter.dirs_made(*sh.mkdirslist(self.log_dir))
        if self.cfg.getboolean('horizon', 'eliminate_pip_gits'):
            fn = sh.joinpths(self.get_option('app_dir'), 'tools', 'pip-requires')
            if sh.isfile(fn):
                new_lines = []
                for line in sh.load_file(fn).splitlines():
                    if line.find("git://") != -1:
                        new_lines.append("# %s" % (line))
                    else:
                        new_lines.append(line)
                sh.write_file(fn, "\n".join(new_lines))

    def _config_fixups(self):
        pass

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        self._setup_db()
        self._sync_db()
        self._setup_blackhole()
        self._config_fixups()

    def _get_apache_user_group(self):
        user = self.cfg.getdefaulted('horizon', 'apache_user', sh.getuser())
        group = self.cfg.getdefaulted('horizon', 'apache_group', sh.getgroupname())
        return (user, group)

    def _get_param_map(self, config_fn):
        # This dict will be used to fill in the configuration
        # params with actual values
        mp = comp.PythonInstallComponent._get_param_map(self, config_fn)
        if config_fn == HORIZON_APACHE_CONF:
            (user, group) = self._get_apache_user_group()
            mp['GROUP'] = group
            mp['USER'] = user
            mp['ACCESS_LOG'] = sh.joinpths(self.log_dir, APACHE_ACCESS_LOG_FN)
            mp['ERROR_LOG'] = sh.joinpths(self.log_dir, APACHE_ERROR_LOG_FN)
            mp['HORIZON_DIR'] = self.get_option('app_dir')
            mp['HORIZON_PORT'] = self.cfg.getdefaulted('horizon', 'port', APACHE_DEF_PORT)
            mp['VPN_DIR'] = sh.joinpths(self.get_option('app_dir'), "vpn")
        else:
            mp['OPENSTACK_HOST'] = self.cfg.get('host', 'ip')
            mp['DB_NAME'] = DB_NAME
            mp['DB_USER'] = self.cfg.getdefaulted('db', 'sql_user', 'root')
            mp['DB_PASSWORD'] = self.cfg.get_password('sql', dbhelper.PASSWORD_PROMPT)
            mp['DB_HOST'] = self.cfg.get("db", "sql_host")
            mp['DB_PORT'] = self.cfg.get("db", "port")
        return mp


class HorizonRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, *args, **kargs)

    def start(self):
        if self._status() != constants.STATUS_STARTED:
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
        if self._status() != constants.STATUS_STOPPED:
            stop_cmd = self.distro.get_command('apache', 'stop')
            sh.execute(*stop_cmd, run_as_root=True, check_exit_code=True)
            return 1
        else:
            return 0

    def _status(self):
        status_cmd = self.distro.get_command('apache', 'status')
        (sysout, stderr) = sh.execute(*status_cmd, run_as_root=True, check_exit_code=False)
        combined = (str(sysout) + str(stderr)).lower()
        if combined.find("is running") != -1:
            return constants.STATUS_STARTED
        elif combined.find("not running") != -1 or \
             combined.find("stopped") != -1 or \
             combined.find('unrecognized') != -1:
            return constants.STATUS_STOPPED
        else:
            return constants.STATUS_UNKNOWN
