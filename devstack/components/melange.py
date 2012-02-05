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

from devstack import cfg
from devstack import component as comp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

LOG = logging.getLogger("devstack.components.melange")

#id
TYPE = settings.MELANGE

#the pkg json files melange requires for installation
REQ_PKGS = ['general.json']

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
    {'cmd': ['%BINDIR%/melange-manage', '--config-file', '%CFGFILE%',
             'db_sync']},
]


class MelangeUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)


class MelangeInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)

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
        cfg_loc = [self.appdir] + CFG_LOC + [ROOT_CONF_REAL_NAME]
        mp['CFGFILE'] = sh.joinpths(*cfg_loc)
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
                config.set('DEFAULT', 'sql_connection', db_dsn)
                with io.BytesIO() as outputstream:
                        config.write(outputstream)
                        outputstream.flush()
                        new_data = ['# Adjusted %s' % (config_fn), outputstream.getvalue()]
                        #TODO can we write to contents here directly?
                        newcontents = utils.joinlinesep(*new_data)
            contents = newcontents
        return contents

    def _get_source_config(self, config_fn):
        if config_fn == ROOT_CONF:
            src_loc = [self.appdir] + CFG_LOC + [config_fn]
            srcfn = sh.joinpths(*src_loc)
            contents = sh.load_file(srcfn)
            return (srcfn, contents)
        else:
            return comp.PkgInstallComponent._get_source_config(self, config_fn)

    def _get_target_config_name(self, config_fn):
        if config_fn == ROOT_CONF:
            tgt_loc = [self.appdir] + CFG_LOC + [ROOT_CONF_REAL_NAME]
            return sh.joinpths(*tgt_loc)
        else:
            return comp.PkgInstallComponent._get_target_config_name(self, config_fn)


class MelangeRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, TYPE, *args, **kargs)


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
    params['description'] = __doc__ or "Handles actions for the melange component."
    out = description.format(**params)
    return out.strip("\n")
