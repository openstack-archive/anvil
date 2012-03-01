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
import time

from devstack import cfg
from devstack import component as comp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

from devstack.components import db

#id
TYPE = settings.MELANGE
LOG = logging.getLogger("devstack.components.melange")

#the pkg json files melange requires for installation
REQ_PKGS = ['general.json', 'melange.json']

#this db will be dropped then created
DB_NAME = 'melange'

#subdirs of the checkout/download
BIN_DIR = 'bin'

#configs
ROOT_CONF = 'melange.conf.sample'
ROOT_CONF_REAL_NAME = 'melange.conf'
CONFIGS = [ROOT_CONF]
CFG_LOC = ['etc', 'melange']

#how we sync melange with the db
DB_SYNC_CMD = [
    {'cmd': ['%BINDIR%/melange-manage', '--config-file=%CFG_FILE%', 'db_sync']},
]

#???
CIDR_CREATE_CMD = [
    {'cmd': ['melange', 'mac_address_range', 'create', 'cidr', '%CIDR_RANGE%']},
]

#what to start
APP_OPTIONS = {
    'melange-server': ['--config-file', '%CFG_FILE%'],
}

#subcomponent that specifies we should make the network cidr using melange
CREATE_CIDR = "create-cidr"
WAIT_ONLINE_TO = settings.WAIT_ALIVE_SECS


class MelangeUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)


class MelangeInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)
        self.cfgdir = sh.joinpths(self.appdir, *CFG_LOC)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "melange_repo"),
            'branch': ("git", "melange_branch"),
        })
        return places

    def _setup_db(self):
        LOG.info("Fixing up database named %s.", DB_NAME)
        db.drop_db(self.cfg, DB_NAME)
        db.create_db(self.cfg, DB_NAME)

    def _get_pkgs(self):
        return list(REQ_PKGS)

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        self._setup_db()
        self._sync_db()

    def _sync_db(self):
        LOG.info("Syncing the database with melange.")
        mp = dict()
        mp['BINDIR'] = self.bindir
        mp['CFG_FILE'] = sh.joinpths(self.cfgdir, ROOT_CONF_REAL_NAME)
        utils.execute_template(*DB_SYNC_CMD, params=mp)

    def _get_config_files(self):
        return list(CONFIGS)

    def _config_adjust(self, contents, config_fn):
        if config_fn == ROOT_CONF:
            newcontents = contents
            with io.BytesIO(contents) as stream:
                config = cfg.IgnoreMissingConfigParser()
                config.readfp(stream)
                db_dsn = self.cfg.get_dbdsn(DB_NAME)
                old_dbsn = config.get('DEFAULT', 'sql_connection')
                if db_dsn != old_dbsn:
                    config.set('DEFAULT', 'sql_connection', db_dsn)
                    with io.BytesIO() as outputstream:
                        config.write(outputstream)
                        outputstream.flush()
                        newcontents = cfg.add_header(config_fn, outputstream.getvalue())
            contents = newcontents
        return contents

    def _get_source_config(self, config_fn):
        if config_fn == ROOT_CONF:
            srcfn = sh.joinpths(self.cfgdir, config_fn)
            contents = sh.load_file(srcfn)
            return (srcfn, contents)
        else:
            return comp.PythonInstallComponent._get_source_config(self, config_fn)

    def _get_target_config_name(self, config_fn):
        if config_fn == ROOT_CONF:
            return sh.joinpths(self.cfgdir, ROOT_CONF_REAL_NAME)
        else:
            return comp.PythonInstallComponent._get_target_config_name(self, config_fn)


class MelangeRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, TYPE, *args, **kargs)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)
        self.cfgdir = sh.joinpths(self.appdir, *CFG_LOC)

    def _get_apps_to_start(self):
        apps = list()
        for app_name in APP_OPTIONS.keys():
            apps.append({
                'name': app_name,
                'path': sh.joinpths(self.bindir, app_name),
            })
        return apps

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)

    def _get_param_map(self, app_name):
        pmap = comp.PythonRuntime._get_param_map(self, app_name)
        pmap['CFG_FILE'] = sh.joinpths(self.cfgdir, ROOT_CONF_REAL_NAME)
        return pmap

    def post_start(self):
        comp.PythonRuntime.post_start(self)
        if CREATE_CIDR in self.component_opts or not self.component_opts:
            LOG.info("Waiting %s seconds so that the melange server can start up before cidr range creation." % (WAIT_ONLINE_TO))
            time.sleep(WAIT_ONLINE_TO)
            mp = dict()
            mp['CIDR_RANGE'] = self.cfg.get('melange', 'm_mac_range')
            utils.execute_template(*CIDR_CREATE_CMD, params=mp)
