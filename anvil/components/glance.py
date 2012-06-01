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
from anvil import component as comp
from anvil import log as logging
from anvil import shell as sh

from anvil.helpers import db as dbhelper
from anvil.helpers import glance as ghelper
from anvil.helpers import keystone as khelper

LOG = logging.getLogger(__name__)

# Config files/sections
API_CONF = "glance-api.conf"
REG_CONF = "glance-registry.conf"
API_PASTE_CONF = 'glance-api-paste.ini'
REG_PASTE_CONF = 'glance-registry-paste.ini'
LOGGING_CONF = "logging.conf"
LOGGING_SOURCE_FN = 'logging.cnf.sample'
POLICY_JSON = 'policy.json'
CONFIGS = [API_CONF, REG_CONF, API_PASTE_CONF,
            REG_PASTE_CONF, POLICY_JSON, LOGGING_CONF]

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

    def pre_install(self):
        comp.PythonInstallComponent.pre_install(self)
        if self.cfg.getboolean('glance', 'eliminate_pip_gits'):
            fn = sh.joinpths(self.app_dir, 'tools', 'pip-requires')
            if sh.isfile(fn):
                new_lines = []
                for line in sh.load_file(fn).splitlines():
                    if line.find("git://") != -1:
                        new_lines.append("# %s" % (line))
                    else:
                        new_lines.append(line)
                sh.write_file(fn, "\n".join(new_lines))

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        self._setup_db()

    def _setup_db(self):
        dbhelper.drop_db(self.cfg, self.distro, DB_NAME)
        dbhelper.create_db(self.cfg, self.distro, DB_NAME, utf8=True)

    def _get_source_config(self, config_fn):
        real_fn = config_fn
        if config_fn == LOGGING_CONF:
            real_fn = LOGGING_SOURCE_FN
        fn = sh.joinpths(self.app_dir, 'etc', real_fn)
        return (fn, sh.load_file(fn))

    def _config_adjust_registry(self, contents, fn):
        params = ghelper.get_shared_params(self.cfg)
        with io.BytesIO(contents) as stream:
            config = cfg.RewritableConfigParser()
            config.readfp(stream)
            config.set('DEFAULT', 'debug', True)
            config.set('DEFAULT', 'verbose', True)
            config.set('DEFAULT', 'bind_port', params['endpoints']['registry']['port'])
            config.remove_option('DEFAULT', 'log_file')
            config.set('DEFAULT', 'sql_connection',
                                dbhelper.fetch_dbdsn(self.cfg, DB_NAME, utf8=True))
            config.set('paste_deploy', 'flavor', 'keystone')
            return config.stringify(fn)
        return contents

    def _config_adjust_paste(self, contents, fn):
        params = khelper.get_shared_params(self.cfg, 'glance')
        with io.BytesIO(contents) as stream:
            config = cfg.RewritableConfigParser()
            config.readfp(stream)
            config.set('filter:authtoken', 'auth_host', params['endpoints']['admin']['host'])
            config.set('filter:authtoken', 'auth_port', params['endpoints']['admin']['port'])
            config.set('filter:authtoken', 'auth_protocol', params['endpoints']['admin']['protocol'])

            config.set('filter:authtoken', 'service_host', params['endpoints']['internal']['host'])
            config.set('filter:authtoken', 'service_port', params['endpoints']['internal']['port'])
            config.set('filter:authtoken', 'service_protocol', params['endpoints']['internal']['protocol'])

            config.set('filter:authtoken', 'admin_tenant_name', params['service_tenant'])
            config.set('filter:authtoken', 'admin_user', params['service_user'])
            config.set('filter:authtoken', 'admin_password', params['service_password'])
            contents = config.stringify(fn)
        return contents

    def _config_adjust_api(self, contents, fn):
        params = ghelper.get_shared_params(self.cfg)
        with io.BytesIO(contents) as stream:
            config = cfg.RewritableConfigParser()
            config.readfp(stream)
            img_store_dir = self._get_image_dir()
            config.set('DEFAULT', 'debug', True)
            config.set('DEFAULT', 'verbose', True)
            config.set('DEFAULT', 'default_store', 'file')
            config.set('DEFAULT', 'filesystem_store_datadir', img_store_dir)
            config.set('DEFAULT', 'bind_port', params['endpoints']['public']['port'])
            config.remove_option('DEFAULT', 'log_file')
            config.set('paste_deploy', 'flavor', 'keystone')
            LOG.info("Ensuring file system store directory %r exists and is empty." % (img_store_dir))
            sh.deldir(img_store_dir)
            self.tracewriter.dirs_made(*sh.mkdirslist(img_store_dir))
            return config.stringify(fn)

    def _config_adjust_logging(self, contents, fn):
        with io.BytesIO(contents) as stream:
            config = cfg.RewritableConfigParser()
            config.readfp(stream)
            config.set('logger_root', 'level', 'DEBUG')
            config.set('logger_root', 'handlers', "devel,production")
            contents = config.stringify(fn)
        return contents

    def _config_param_replace(self, config_fn, contents, parameters):
        if config_fn in [REG_CONF, REG_PASTE_CONF, API_CONF, API_PASTE_CONF, LOGGING_CONF]:
            # We handle these ourselves
            return contents
        else:
            return comp.PythonInstallComponent._config_param_replace(self, config_fn, contents, parameters)

    def _config_adjust(self, contents, name):
        if name == REG_CONF:
            return self._config_adjust_registry(contents, name)
        elif name == REG_PASTE_CONF:
            return self._config_adjust_paste(contents, name)
        elif name == API_CONF:
            return self._config_adjust_api(contents, name)
        elif name == API_PASTE_CONF:
            return self._config_adjust_paste(contents, name)
        elif name == LOGGING_CONF:
            return self._config_adjust_logging(contents, name)
        else:
            return contents

    def _get_image_dir(self):
        # This might be changed often so make it a function
        return sh.joinpths(self.component_dir, 'images')


class GlanceRuntime(GlanceMixin, comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.app_dir, BIN_DIR)
        self.wait_time = max(self.cfg.getint('DEFAULT', 'service_wait_seconds'), 1)
        self.do_upload = True
        if 'no-load-images' in self.options:
            self.do_upload = False

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

    def _get_image_urls(self):
        uris = self.cfg.getdefaulted('glance', 'image_urls', '').split(",")
        return [u.strip() for u in uris if len(u.strip())]

    def post_start(self):
        comp.PythonRuntime.post_start(self)
        if self.do_upload:
            # Install any images that need activating...
            LOG.info("Waiting %s seconds so that glance can start up before image install." % (self.wait_time))
            sh.sleep(self.wait_time)
            params = {}
            params['glance'] = ghelper.get_shared_params(self.cfg)
            params['keystone'] = khelper.get_shared_params(self.cfg, 'glance')
            ghelper.UploadService(params).install(self._get_image_urls())
