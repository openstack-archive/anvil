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
from devstack import shell as sh

from devstack.components import db
from devstack.components import keystone

from devstack.image import uploader

LOG = logging.getLogger("devstack.components.glance")

# Config files/sections
API_CONF = "glance-api.conf"
REG_CONF = "glance-registry.conf"
API_PASTE_CONF = 'glance-api-paste.ini'
REG_PASTE_CONF = 'glance-registry-paste.ini'
SCRUB_CONF = 'glance-scrubber.conf'
SCRUB_PASTE_CONF = 'glance-scrubber-paste.ini'
LOGGING_CONF = "logging.conf"
LOGGING_SOURCE_FN = 'logging.cnf.sample'
POLICY_JSON = 'policy.json'
CONFIGS = [API_CONF, REG_CONF, API_PASTE_CONF,
            REG_PASTE_CONF, POLICY_JSON, LOGGING_CONF,
            SCRUB_CONF, SCRUB_PASTE_CONF]
READ_CONFIGS = [API_CONF, REG_CONF, API_PASTE_CONF,
                REG_PASTE_CONF, SCRUB_CONF, SCRUB_PASTE_CONF]

# Reg, api, scrub are here as possible subsystems
GAPI = "api"
GREG = "reg"
GSCR = 'scrub'

# This db will be dropped and created
DB_NAME = "glance"

# What applications to start
APP_OPTIONS = {
    'glance-api': ['--config-file', sh.joinpths('%CONFIG_DIR%', API_CONF)],
    'glance-registry': ['--config-file', sh.joinpths('%CONFIG_DIR%', REG_CONF)],
    'glance-scrubber': ['--config-file', sh.joinpths('%CONFIG_DIR%', REG_CONF)],
}

# How the subcompoent small name translates to an actual app
SUB_TO_APP = {
    GAPI: 'glance-api',
    GREG: 'glance-registry',
    GSCR: 'glance-scrubber',
}

# Subdirs of the downloaded (we are overriding the original)
BIN_DIR = 'bin'


class GlanceMixin(object):

    def known_options(self):
        return set(['no-load-images'])

    def known_subsystems(self):
        return SUB_TO_APP.keys()

    def _get_config_files(self):
        return list(CONFIGS)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "glance_repo"),
            'branch': ("git", "glance_branch"),
        })
        return places


class GlanceUninstaller(GlanceMixin, comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)


class GlanceInstaller(GlanceMixin, comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        self._setup_db()

    def _setup_db(self):
        LOG.info("Fixing up database named %r", DB_NAME)
        db.drop_db(self.cfg, self.pw_gen, self.distro, DB_NAME)
        db.create_db(self.cfg, self.pw_gen, self.distro, DB_NAME)

    def _get_source_config(self, config_fn):
        if config_fn == POLICY_JSON:
            # FIXME, maybe we shouldn't be sucking this from the checkout??
            fn = sh.joinpths(self.app_dir, 'etc', POLICY_JSON)
            contents = sh.load_file(fn)
            return (fn, contents)
        elif config_fn == LOGGING_CONF:
            # FIXME, maybe we shouldn't be sucking this from the checkout??
            fn = sh.joinpths(self.app_dir, 'etc', LOGGING_SOURCE_FN)
            contents = sh.load_file(fn)
            return (fn, contents)
        return comp.PythonInstallComponent._get_source_config(self, config_fn)

    def _config_adjust(self, contents, name):
        # Even bother opening??
        if name not in READ_CONFIGS:
            return contents
        # Use config parser and
        # then extract known configs that
        # will need locations/directories/files made (or touched)...
        with io.BytesIO(contents) as stream:
            config = cfg.IgnoreMissingConfigParser()
            config.readfp(stream)
            if config.getboolean('default', 'image_cache_enabled'):
                cache_dir = config.get('default', "image_cache_datadir")
                if cache_dir:
                    LOG.info("Ensuring image cache data directory %r exists (and is empty)" % (cache_dir))
                    # Destroy then recreate the image cache directory
                    sh.deldir(cache_dir)
                    self.tracewriter.dirs_made(*sh.mkdirslist(cache_dir))
            if config.get('default', 'default_store') == 'file':
                file_dir = config.get('default', 'filesystem_store_datadir')
                if file_dir:
                    LOG.info("Ensuring file system store directory %r exists and is empty." % (file_dir))
                    # Delete existing images
                    # and recreate the image directory
                    sh.deldir(file_dir)
                    self.tracewriter.dirs_made(*sh.mkdirslist(file_dir))
            log_filename = config.get('default', 'log_file')
            if log_filename:
                LOG.info("Ensuring log file %r exists and is empty." % (log_filename))
                log_dir = sh.dirname(log_filename)
                if log_dir:
                    LOG.info("Ensuring log directory %r exists." % (log_dir))
                    self.tracewriter.dirs_made(*sh.mkdirslist(log_dir))
                # Destroy then recreate it (the log file)
                sh.unlink(log_filename)
                self.tracewriter.file_touched(sh.touch_file(log_filename))
            if config.getboolean('default', 'delayed_delete'):
                data_dir = config.get('default', 'scrubber_datadir')
                if data_dir:
                    LOG.info("Ensuring scrubber data dir %r exists and is empty." % (data_dir))
                    # Destroy then recreate the scrubber data directory
                    sh.deldir(data_dir)
                    self.tracewriter.dirs_made(*sh.mkdirslist(data_dir))
        # Nothing modified so just return the original
        return contents

    def _get_image_dir(self):
        # This might be changed often so make it a function
        return sh.joinpths(self.component_dir, 'images')

    def _get_param_map(self, config_fn):
        # This dict will be used to fill in the configuration
        # params with actual values
        mp = comp.PythonInstallComponent._get_param_map(self, config_fn)
        mp['IMG_DIR'] = self._get_image_dir()
        mp['SYSLOG'] = self.cfg.getboolean("default", "syslog")
        mp['SQL_CONN'] = db.fetch_dbdsn(self.cfg, self.pw_gen, DB_NAME)
        mp['SERVICE_HOST'] = self.cfg.get('host', 'ip')
        mp['HOST_IP'] = self.cfg.get('host', 'ip')
        mp.update(keystone.get_shared_params(self.cfg, self.pw_gen, 'glance'))
        return mp


class GlanceRuntime(GlanceMixin, comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.app_dir, BIN_DIR)
        self.wait_time = max(self.cfg.getint('default', 'service_wait_seconds'), 1)

    def _get_apps_to_start(self):
        apps = list()
        for subsys in self.desired_subsystems:
            apps.append({
                'name': SUB_TO_APP[subsys],
                'path': sh.joinpths(self.bin_dir, SUB_TO_APP[subsys]),
            })
        return apps

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)

    def post_start(self):
        comp.PythonRuntime.post_start(self)
        if 'no-load-images' in self.options:
            pass
        else:
            # Install any images that need activating...
            # TODO: make this less cheesy - need to wait till glance goes online
            LOG.info("Waiting %s seconds so that glance can start up before image install." % (self.wait_time))
            sh.sleep(self.wait_time)
            uploader.Service(self.cfg, self.pw_gen).install()
