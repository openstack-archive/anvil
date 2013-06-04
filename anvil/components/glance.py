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
from anvil import log as logging
from anvil import utils

from anvil.utils import OrderedDict

from anvil.components import base_install as binstall
from anvil.components import base_runtime as bruntime
from anvil.components import base_testing as btesting

from anvil.components.helpers import glance as ghelper
from anvil.components.helpers import keystone as khelper

from anvil.components.configurators import glance as gconf

LOG = logging.getLogger(__name__)

# Sync db command
SYNC_DB_CMD = ['sudo', '-u', 'glance', '/usr/bin/glance-manage',
               '--debug', '-v',
               # Available commands:
               'db_sync']


class GlanceInstaller(binstall.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        binstall.PythonInstallComponent.__init__(self, *args, **kargs)
        self.configurator = gconf.GlanceConfigurator(self)

    def post_install(self):
        binstall.PythonInstallComponent.post_install(self)
        if self.get_bool_option('db-sync'):
            self.configurator.setup_db()
            self._sync_db()

    def _sync_db(self):
        LOG.info("Syncing glance to database: %s", colorizer.quote(self.configurator.DB_NAME))
        cmds = [{'cmd': SYNC_DB_CMD}]
        utils.execute_template(*cmds, cwd=self.bin_dir, params=self.config_params(None))

    @property
    def env_exports(self):
        to_set = OrderedDict()
        params = ghelper.get_shared_params(**self.options)
        for (endpoint, details) in params['endpoints'].items():
            to_set[("GLANCE_%s_URI" % (endpoint.upper()))] = details['uri']
        return to_set


class GlanceRuntime(bruntime.OpenStackRuntime):
    def _get_image_urls(self):
        uris = self.get_option('image_urls', default_value=[])
        return [u.strip() for u in uris if len(u.strip())]

    def post_start(self):
        bruntime.OpenStackRuntime.post_start(self)
        if self.get_bool_option('load-images'):
            # Install any images that need activating...
            self.wait_active()
            params = {}
            params['glance'] = ghelper.get_shared_params(**self.options)
            params['keystone'] = khelper.get_shared_params(ip=self.get_option('ip'),
                                                           service_user='glance',
                                                           **utils.merge_dicts(self.get_option('keystone'),
                                                                               khelper.get_shared_passwords(self)))
            cache_dir = self.get_option('image_cache_dir')
            if cache_dir:
                params['cache_dir'] = cache_dir
            ghelper.UploadService(**params).install(self._get_image_urls())


class GlanceTester(btesting.PythonTestingComponent):
    # NOTE: only run the unit tests
    def _get_test_command(self):
        base_cmd = btesting.PythonTestingComponent._get_test_command(self)
        base_cmd = base_cmd + ['--unittests-only']
        return base_cmd
