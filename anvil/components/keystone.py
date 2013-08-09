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
from anvil import shell as sh
from anvil import utils

from anvil.utils import OrderedDict

from anvil.components import base_install as binstall
from anvil.components import base_runtime as bruntime
from anvil.components import base_testing as btesting

from anvil.components.helpers import cinder as chelper
from anvil.components.helpers import glance as ghelper
from anvil.components.helpers import keystone as khelper
from anvil.components.helpers import neutron as net_helper
from anvil.components.helpers import nova as nhelper

from anvil.components.configurators import keystone as kconf

LOG = logging.getLogger(__name__)

# This yaml file controls keystone initialization
INIT_WHAT_FN = 'init_what.yaml'

# Existence of this file signifies that initialization ran
INIT_WHAT_HAPPENED = "keystone.inited.yaml"

# Invoking the keystone manage command uses this template
MANAGE_CMD = ['sudo', '-u', 'keystone', '/usr/bin/keystone-manage',
              '--debug', '-v']


class KeystoneInstaller(binstall.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        binstall.PythonInstallComponent.__init__(self, *args, **kargs)
        self.configurator = kconf.KeystoneConfigurator(self)

    def post_install(self):
        binstall.PythonInstallComponent.post_install(self)
        if self.get_bool_option('db-sync'):
            self.configurator.setup_db()
            self._sync_db()
        if self.get_bool_option('enable-pki'):
            self._setup_pki()

    def _sync_db(self):
        LOG.info("Syncing keystone to database: %s", colorizer.quote(self.configurator.DB_NAME))
        sync_cmd = MANAGE_CMD + ['db_sync']
        cmds = [{'cmd': sync_cmd}]
        utils.execute_template(*cmds, cwd=self.bin_dir, params=self.config_params(None))

    @property
    def env_exports(self):
        params = khelper.get_shared_params(**utils.merge_dicts(self.options,
                                                               khelper.get_shared_passwords(self)))
        to_set = OrderedDict()
        to_set['OS_PASSWORD'] = params['admin_password']
        to_set['OS_TENANT_NAME'] = params['admin_tenant']
        to_set['OS_USERNAME'] = params['admin_user']
        to_set['OS_AUTH_URL'] = params['endpoints']['public']['uri']
        for (endpoint, details) in params['endpoints'].items():
            if endpoint.find('templated') != -1:
                continue
            to_set[("KEYSTONE_%s_URI" % (endpoint.upper()))] = details['uri']
        return to_set

    def _setup_pki(self):
        LOG.info("Setting up keystone's pki support.")
        for value in kconf.PKI_FILES.values():
            sh.mkdirslist(sh.dirname(sh.joinpths(self.configurator.link_dir, value)),
                          tracewriter=self.tracewriter)
        pki_cmd = MANAGE_CMD + ['pki_setup']
        cmds = [{'cmd': pki_cmd}]
        utils.execute_template(*cmds, cwd=self.bin_dir, params=self.config_params(None))

    def warm_configs(self):
        khelper.get_shared_passwords(self)


class KeystoneUninstaller(binstall.PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        binstall.PkgUninstallComponent.__init__(self, *args, **kargs)
        self.init_fn = sh.joinpths(self.get_option('trace_dir'), INIT_WHAT_HAPPENED)

    def unconfigure(self):
        if sh.isfile(self.init_fn):
            sh.unlink(self.init_fn)


class KeystoneRuntime(bruntime.OpenStackRuntime):
    def __init__(self, *args, **kargs):
        bruntime.OpenStackRuntime.__init__(self, *args, **kargs)
        self.init_fn = sh.joinpths(self.get_option('trace_dir'), INIT_WHAT_HAPPENED)

    def post_start(self):
        if not sh.isfile(self.init_fn) and self.get_bool_option('do-init'):
            self.wait_active()
            LOG.info("Running commands to initialize keystone.")
            (fn, contents) = utils.load_template(self.name, INIT_WHAT_FN)
            LOG.debug("Initializing with contents of %s", fn)
            params = {}
            params['keystone'] = khelper.get_shared_params(**utils.merge_dicts(self.options, khelper.get_shared_passwords(self)))
            params['glance'] = ghelper.get_shared_params(ip=self.get_option('ip'), **self.get_option('glance'))
            params['nova'] = nhelper.get_shared_params(ip=self.get_option('ip'), **self.get_option('nova'))
            params['neutron'] = net_helper.get_shared_params(ip=self.get_option('ip'), **self.get_option('neutron'))
            params['cinder'] = chelper.get_shared_params(ip=self.get_option('ip'), **self.get_option('cinder'))
            wait_urls = [
                params['keystone']['endpoints']['admin']['uri'],
                params['keystone']['endpoints']['public']['uri'],
            ]
            for url in wait_urls:
                utils.wait_for_url(url)
            init_what = utils.load_yaml_text(contents)
            init_what = utils.expand_template_deep(init_what, params)
            khelper.Initializer(params['keystone']['service_token'],
                                params['keystone']['endpoints']['admin']['uri']).initialize(**init_what)
            # Writing this makes sure that we don't init again
            sh.write_file(self.init_fn, utils.prettify_yaml(init_what))
            LOG.info("If you wish to re-run initialization, delete %s", colorizer.quote(self.init_fn))


class KeystoneTester(btesting.PythonTestingComponent):
    # Disable the keystone client integration tests
    def _get_test_command(self):
        base_cmd = btesting.PythonTestingComponent._get_test_command(self)
        base_cmd = base_cmd + ['-xintegration']
        return base_cmd
