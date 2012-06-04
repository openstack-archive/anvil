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

import io

from anvil import cfg
from anvil import colorizer
from anvil import component as comp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.helpers import db as dbhelper

LOG = logging.getLogger(__name__)

# This db will be dropped then created
DB_NAME = 'melange'

# Subdirs of the checkout/download
BIN_DIR = 'bin'

# Basic configs
ROOT_CONF = 'melange.conf.sample'
ROOT_CONF_REAL_NAME = 'melange.conf'
CONFIGS = [ROOT_CONF]

# Sensible defaults
DEF_CIDR_RANGE = 'FE-EE-DD-00-00-00/24'

# How we sync melange with the db
DB_SYNC_CMD = [
    {'cmd': ['%BIN_DIR%/melange-manage', '--config-file=%CFG_FILE%', 'db_sync']},
]

# TODO: ???
CIDR_CREATE_CMD = [
    {'cmd': ['melange', '--config-file=%CFG_FILE%', 'mac_address_range', 'create', 'cidr', '%CIDR_RANGE%']},
]

# What to start
APP_OPTIONS = {
    'melange-server': ['--config-file=%CFG_FILE%'],
}


class MelangeUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)


class MelangeInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.get_option('app_dir'), BIN_DIR)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "melange_repo"),
            'branch': ("git", "melange_branch"),
        })
        return places

    def _setup_db(self):
        dbhelper.drop_db(self.cfg, self.distro, DB_NAME)
        dbhelper.create_db(self.cfg, self.distro, DB_NAME, utf8=True)

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        self._setup_db()
        self._sync_db()

    def _sync_db(self):
        LOG.info("Syncing melange to database: %s", colorizer.quote(DB_NAME))
        utils.execute_template(*DB_SYNC_CMD, params=self._get_param_map(None))

    def _get_param_map(self, config_fn):
        mp = comp.PythonInstallComponent._get_param_map(self, config_fn)
        mp['CFG_FILE'] = sh.joinpths(self.get_option('cfg_dir'), ROOT_CONF_REAL_NAME)
        mp['BIN_DIR'] = self.bin_dir
        return mp

    def _get_config_files(self):
        return list(CONFIGS)

    def _config_adjust(self, contents, config_fn):
        if config_fn == ROOT_CONF:
            with io.BytesIO(contents) as stream:
                config = cfg.RewritableConfigParser()
                config.readfp(stream)
                config.set('DEFAULT', 'sql_connection', dbhelper.fetch_dbdsn(self.cfg, DB_NAME, utf8=True))
                config.set('DEFAULT', 'verbose', True)
                config.set('DEFAULT', 'debug', True)
                contents = config.stringify(config_fn)
        return contents

    def _get_source_config(self, config_fn):
        if config_fn == ROOT_CONF:
            # FIXME, maybe we shouldn't be sucking this from the checkout??
            fn = sh.joinpths(self.get_option('app_dir'), 'etc', 'melange', config_fn)
            contents = sh.load_file(fn)
            return (fn, contents)
        return comp.PythonInstallComponent._get_source_config(self, config_fn)

    def _get_target_config_name(self, config_fn):
        if config_fn == ROOT_CONF:
            return sh.joinpths(self.get_option('cfg_dir'), ROOT_CONF_REAL_NAME)
        else:
            return comp.PythonInstallComponent._get_target_config_name(self, config_fn)


class MelangeRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.get_option('app_dir'), BIN_DIR)
        self.wait_time = max(self.cfg.getint('DEFAULT', 'service_wait_seconds'), 1)

    def _get_apps_to_start(self):
        apps = list()
        for app_name in APP_OPTIONS.keys():
            apps.append({
                'name': app_name,
                'path': sh.joinpths(self.bin_dir, app_name),
            })
        return apps

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)

    def _get_param_map(self, app_name):
        mp = comp.PythonRuntime._get_param_map(self, app_name)
        mp['CFG_FILE'] = sh.joinpths(self.get_option('cfg_dir'), ROOT_CONF_REAL_NAME)
        return mp

    def post_start(self):
        comp.PythonRuntime.post_start(self)
        if self.get_option('create-cidr'):
            LOG.info("Waiting %s seconds so that the melange server can start up before cidr range creation." % (self.wait_time))
            sh.sleep(self.wait_time)
            mp = dict()
            mp['CIDR_RANGE'] = self.cfg.getdefaulted('melange', 'm_mac_range', DEF_CIDR_RANGE)
            utils.execute_template(*CIDR_CREATE_CMD, params=mp)
