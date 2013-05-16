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

from anvil import components as comp
from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

import binascii
import os
import re

LOG = logging.getLogger(__name__)

# See https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-SECRET_KEY
#
# Needs to be a multiple of 2 for our usage...
SECRET_KEY_LEN = 10

# Config files messed with...
HORIZON_LOCAL_SETTINGS_CONF = "local_settings.py"
HORIZON_APACHE_CONF = 'horizon_apache.conf'
CONFIGS = [HORIZON_LOCAL_SETTINGS_CONF, HORIZON_APACHE_CONF]

# Users which apache may not like starting as..
BAD_APACHE_USERS = ['root']


class HorizonUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)


class HorizonInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)
        self.blackhole_dir = sh.joinpths(self.get_option('app_dir'), '.blackhole')
        self.access_log = sh.joinpths('/var/log/',
                                      self.distro.get_command_config('apache', 'name'),
                                      'horizon_access.log')
        self.error_log = sh.joinpths('/var/log/',
                                     self.distro.get_command_config('apache', 'name'),
                                     'horizon_error.log')

    def _filter_pip_requires(self, fn, lines):
        # Knock off all nova, quantum, swift, keystone, cinder
        # clients since anvil will be making sure those are installed
        # instead of asking setup.py to do it...
        return [l for l in lines if not re.search(r'([n|q|s|k|g|c]\w+client)', l, re.I)]

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
        if config_name == HORIZON_LOCAL_SETTINGS_CONF:
            return sh.joinpths(self.get_option('app_dir'), 'openstack_dashboard', 'local', config_name)
        else:
            return comp.PythonInstallComponent.target_config(self, config_name)

    @property
    def config_files(self):
        return list(CONFIGS)

    def _setup_blackhole(self):
        # Create an empty directory that apache uses as docroot
        sh.mkdirslist(self.blackhole_dir, tracewriter=self.tracewriter)

    def _setup_logs(self, clear=False):
        log_fns = [self.access_log, self.error_log]
        utils.log_iterable(log_fns, logger=LOG,
                           header="Adjusting %s log files" % (len(log_fns)))
        for fn in log_fns:
            with sh.Rooted(True):
                if clear:
                    sh.unlink(fn, True)
                sh.touch_file(fn, die_if_there=False, tracewriter=self.tracewriter)
                sh.chmod(fn, 0666)
        return len(log_fns)

    def _configure_files(self):
        am = comp.PythonInstallComponent._configure_files(self)
        am += self._setup_logs(self.get_bool_option('clear-logs'))
        return am

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
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
            if SECRET_KEY_LEN <= 0:
                mp['SECRET_KEY'] = ''
            else:
                mp['SECRET_KEY'] = binascii.b2a_hex(os.urandom(SECRET_KEY_LEN / 2))
        return mp


class HorizonRuntime(comp.ProgramRuntime):
    def start(self):
        if self.statii()[0].status != comp.STATUS_STARTED:
            self._run_action('start')
            return 1
        else:
            return 0

    def _run_action(self, action, check_exit_code=True):
        cmd = self.distro.get_command('apache', action)
        if not cmd:
            raise NotImplementedError("No distro command provided to perform action %r" % (action))
        return sh.execute(*cmd, run_as_root=True, check_exit_code=check_exit_code)

    def restart(self):
        self._run_action('restart')
        return 1

    def stop(self):
        if self.statii()[0].status != comp.STATUS_STOPPED:
            self._run_action('stop')
            return 1
        else:
            return 0

    def statii(self):
        (sysout, stderr) = self._run_action('status', check_exit_code=False)
        combined = (sysout + stderr).lower()
        st = comp.STATUS_UNKNOWN
        if combined.find("is running") != -1:
            st = comp.STATUS_STARTED
        elif utils.has_any(combined, 'stopped', 'unrecognized', 'not running'):
            st = comp.STATUS_STOPPED
        return [
            comp.ProgramStatus(name='apache',
                               status=st,
                               details={
                                   'STDOUT': sysout,
                                   'STDERR': stderr,
                               }),
        ]
