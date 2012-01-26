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
from devstack.components import db
from devstack.components import keystone
from devstack.image import creator

LOG = logging.getLogger("devstack.components.glance")

#id
TYPE = settings.GLANCE

#config files/sections
API_CONF = "glance-api.conf"
REG_CONF = "glance-registry.conf"
API_PASTE_CONF = 'glance-api-paste.ini'
REG_PASTE_CONF = 'glance-registry-paste.ini'
CONFIGS = [API_CONF, REG_CONF, API_PASTE_CONF, REG_PASTE_CONF]
CFG_SECTION = 'DEFAULT'

#this db will be dropped and created
DB_NAME = "glance"

#special subcomponents that is used in starting to know that images should be uploaded
IMG_START = "upload-images"

#what to start
APP_OPTIONS = {
    'glance-api': ['--config-file', sh.joinpths('%ROOT%', "etc", API_CONF)],
    'glance-registry': ['--config-file', sh.joinpths('%ROOT%', "etc", REG_CONF)]
}

#subdirs of the downloaded
CONFIG_DIR = 'etc'
BIN_DIR = 'bin'


class GlanceUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)


class GlanceRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)

    def _get_apps_to_start(self):
        apps = list()
        for app_name in APP_OPTIONS.keys():
            apps.append({
                'name': app_name,
                'path': sh.joinpths(self.appdir, BIN_DIR, app_name),
            })
        return apps

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)

    def post_start(self):
        comp.PythonRuntime.post_start(self)
        if IMG_START in self.component_opts:
            #install any images that need activating...
            creator.ImageCreationService(self.cfg).install()


class GlanceInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.git_loc = self.cfg.get("git", "glance_repo")
        self.git_branch = self.cfg.get("git", "glance_branch")
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)

    def _get_download_locations(self):
        places = comp.PythonInstallComponent._get_download_locations(self)
        places.append({
            'uri': self.git_loc,
            'branch': self.git_branch,
        })
        return places

    def _get_config_files(self):
        #these are the config files we will be adjusting
        return list(CONFIGS)

    def post_install(self):
        parent_result = comp.PythonInstallComponent.post_install(self)
        self._setup_db()
        return parent_result

    def _setup_db(self):
        LOG.info("Fixing up database named %s", DB_NAME)
        db.drop_db(self.cfg, DB_NAME)
        db.create_db(self.cfg, DB_NAME)

    def _config_adjust(self, contents, name):
        if name not in CONFIGS:
            return contents
        #use config parser and
        #then extract known configs that
        #will need locations/directories/files made (or touched)...
        with io.BytesIO(contents) as stream:
            config = cfg.IgnoreMissingConfigParser()
            config.readfp(stream)
            if config.getboolean('image_cache_enabled', CFG_SECTION):
                cache_dir = config.get("image_cache_datadir", CFG_SECTION)
                if cache_dir:
                    LOG.info("Ensuring image cache data directory %s exists "\
                             "(and is empty)" % (cache_dir))
                    #destroy then recreate the image cache directory
                    sh.deldir(cache_dir)
                    self.tracewriter.make_dir(cache_dir)
            if config.get('default_store', CFG_SECTION) == 'file':
                file_dir = config.get('filesystem_store_datadir', CFG_SECTION)
                if file_dir:
                    LOG.info("Ensuring file system store directory %s exists and is empty" % (file_dir))
                    #delete existing images
                    #and recreate the image directory
                    sh.deldir(file_dir)
                    self.tracewriter.make_dir(file_dir)
            log_filename = config.get('log_file', CFG_SECTION)
            if log_filename:
                LOG.info("Ensuring log file %s exists and is empty" % (log_filename))
                log_dir = sh.dirname(log_filename)
                if log_dir:
                    LOG.info("Ensuring log directory %s exists" % (log_dir))
                    self.tracewriter.make_dir(log_dir)
                #destroy then recreate it (the log file)
                sh.unlink(log_filename)
                sh.touch_file(log_filename)
                self.tracewriter.file_touched(log_filename)
            if config.getboolean('delayed_delete', CFG_SECTION):
                data_dir = config.get('scrubber_datadir', CFG_SECTION)
                if data_dir:
                    LOG.info("Ensuring scrubber data dir %s exists and is empty" % (data_dir))
                    #destroy then recreate the scrubber data directory
                    sh.deldir(data_dir)
                    self.tracewriter.make_dir(data_dir)
            #we might need to handle more in the future...
        #nothing modified so just return the original
        return contents

    def _get_param_map(self, config_fn):
        #this dict will be used to fill in the configuration
        #params with actual values
        mp = dict()
        mp['DEST'] = self.appdir
        mp['SYSLOG'] = self.cfg.getboolean("default", "syslog")
        mp['SQL_CONN'] = self.cfg.get_dbdsn(DB_NAME)
        mp['SERVICE_HOST'] = self.cfg.get('host', 'ip')
        mp['HOST_IP'] = self.cfg.get('host', 'ip')
        mp.update(keystone.get_shared_params(self.cfg))
        return mp


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
    params['description'] = __doc__ or "Handles actions for the glance component."
    out = description.format(**params)
    return out.strip("\n")
