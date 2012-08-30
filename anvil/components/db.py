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

import abc

LOG = logging.getLogger(__name__)

# Need to reset pw to blank since this distributions don't seem to
# always reset it when u uninstall the db
RESET_BASE_PW = ''

# Copies from helper
BASE_ERROR = dbhelper.BASE_ERROR


class DBUninstaller(comp.PkgUninstallComponent):

    def __init__(self, *args, **kargs):
        comp.PkgUninstallComponent.__init__(self, *args, **kargs)
        self.runtime = self.siblings.get('running')

    def warm_configs(self):
        dbhelper.get_shared_passwords(self)

    def pre_uninstall(self):
        dbtype = self.get_option("type")
        dbactions = self.distro.get_command_config(dbtype, quiet=True)
        try:
            if dbactions:
                LOG.info(("Attempting to reset your db password to %s so"
                          " that we can set it the next time you install."), colorizer.quote(RESET_BASE_PW))
                pwd_cmd = self.distro.get_command(dbtype, 'set_pwd')
                if pwd_cmd:
                    LOG.info("Ensuring your database is started before we operate on it.")
                    self.runtime.start()
                    self.runtime.wait_active()
                    params = {
                        'OLD_PASSWORD': dbhelper.get_shared_passwords(self)['pw'],
                        'NEW_PASSWORD': RESET_BASE_PW,
                        'USER': self.get_option("user", default_value='root'),
                    }
                    cmds = [{'cmd': pwd_cmd}]
                    utils.execute_template(*cmds, params=params)
        except IOError:
            LOG.warn(("Could not reset the database password. You might have to manually "
                      "reset the password to %s before the next install"), colorizer.quote(RESET_BASE_PW))


class DBInstaller(comp.PkgInstallComponent):
    __meta__ = abc.ABCMeta

    def __init__(self, *args, **kargs):
        comp.PkgInstallComponent.__init__(self, *args, **kargs)
        self.runtime = self.siblings.get('running')

    def config_params(self, config_fn):
        # This dictionary will be used for parameter replacement
        # In pre-install and post-install sections
        mp = comp.PkgInstallComponent.config_params(self, config_fn)
        mp.update({
            'PASSWORD': dbhelper.get_shared_passwords(self)['pw'],
            'BOOT_START': "true",
            'USER': self.get_option("user", default_value='root'),
            'SERVICE_HOST': self.get_option('ip'),
            'HOST_IP': self.get_option('ip'),
        })
        return mp

    def warm_configs(self):
        dbhelper.get_shared_passwords(self)

    @abc.abstractmethod
    def _configure_db_confs(self):
        pass

    def post_install(self):
        comp.PkgInstallComponent.post_install(self)

        # Fix up the db configs
        self._configure_db_confs()

        # Extra actions to ensure we are granted access
        dbtype = self.get_option("type")
        dbactions = self.distro.get_command_config(dbtype, quiet=True)

        # Set your password
        try:
            if dbactions:
                pwd_cmd = self.distro.get_command(dbtype, 'set_pwd')
                if pwd_cmd:
                    LOG.info(("Attempting to set your db password"
                              " just incase it wasn't set previously."))
                    LOG.info("Ensuring your database is started before we operate on it.")
                    self.runtime.start()
                    self.runtime.wait_active()
                    params = {
                        'NEW_PASSWORD': dbhelper.get_shared_passwords(self)['pw'],
                        'USER': self.get_option("user", default_value='root'),
                        'OLD_PASSWORD': RESET_BASE_PW,
                    }
                    cmds = [{'cmd': pwd_cmd}]
                    utils.execute_template(*cmds, params=params)
        except IOError:
            LOG.warn(("Couldn't set your db password. It might have already been "
                       "set by a previous process."))

        # Ensure access granted
        dbhelper.grant_permissions(dbtype,
                                   distro=self.distro,
                                   user=self.get_option("user", default_value='root'),
                                   restart_func=self.runtime.restart,
                                   **dbhelper.get_shared_passwords(self))


class DBRuntime(comp.ProgramRuntime):
    def __init__(self, *args, **kargs):
        comp.ProgramRuntime.__init__(self, *args, **kargs)

    def _get_run_actions(self, act, exception_cls):
        db_type = self.get_option("type")
        distro_options = self.distro.get_command_config(db_type)
        if distro_options is None:
            raise NotImplementedError(BASE_ERROR % (act, db_type))
        return self.distro.get_command(db_type, act)

    @property
    def apps_to_start(self):
        db_type = self.get_option("type")
        return [db_type]

    def start(self):
        if self.status()[0].status != comp.STATUS_STARTED:
            start_cmd = self._get_run_actions('start', excp.StartException)
            sh.execute(*start_cmd, run_as_root=True, check_exit_code=True)
            return 1
        else:
            return 0

    def stop(self):
        if self.status()[0].status != comp.STATUS_STOPPED:
            stop_cmd = self._get_run_actions('stop', excp.StopException)
            sh.execute(*stop_cmd, run_as_root=True, check_exit_code=True)
            return 1
        else:
            return 0

    def restart(self):
        LOG.info("Restarting your database.")
        restart_cmd = self._get_run_actions('restart', excp.RestartException)
        sh.execute(*restart_cmd, run_as_root=True, check_exit_code=True)
        return 1

    def status(self):
        status_cmd = self._get_run_actions('status', excp.StatusException)
        (sysout, stderr) = sh.execute(*status_cmd, run_as_root=True, check_exit_code=False)
        combined = (sysout + stderr).lower()
        st = comp.STATUS_UNKNOWN
        if combined.find("running") != -1:
            st = comp.STATUS_STARTED
        elif utils.has_any(combined, 'stop', 'unrecognized'):
            st = comp.STATUS_STOPPED
        return [
            comp.ProgramStatus(name=self.get_option("type"),
                               status=st,
                               details=(sysout + stderr).strip()),
        ]
