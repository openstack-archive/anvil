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
from anvil import components as comp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.utils import OrderedDict

from anvil.components.helpers import db as dbhelper
from anvil.components.helpers import glance as ghelper
from anvil.components.helpers import keystone as khelper
from anvil.components.helpers import nova as nhelper
from anvil.components.helpers import quantum as qhelper
from anvil.components.helpers import cinder as chelper

LOG = logging.getLogger(__name__)

# This db will be dropped then created
DB_NAME = "keystone"

# This yaml file controls keystone initialization
INIT_WHAT_FN = 'init_what.yaml'

# Existence of this file signifies that initialization ran
INIT_WHAT_HAPPENED = "keystone.inited.yaml"

# Configuration files keystone expects...
ROOT_CONF = "keystone.conf"
LOGGING_CONF = "logging.conf"
POLICY_JSON = 'policy.json'
CONFIGS = [ROOT_CONF, LOGGING_CONF, POLICY_JSON]

# Invoking the keystone manage command uses this template
MANAGE_CMD = [sh.joinpths('$BIN_DIR', 'keystone-manage'),
                '--config-file=$CONFIG_FILE',
                '--debug', '-v']

# PKI base files
PKI_FILES = {
    'ca_certs': 'ssl/certs/ca.pem',
    'keyfile': 'ssl/private/signing_key.pem',
    'certfile': 'ssl/certs/signing_cert.pem',
}


class KeystoneUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)


class KeystoneInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.get_option('app_dir'), 'bin')

    def _filter_pip_requires(self, fn, lines):
        return [l for l in lines
                # Take out entries that aren't really always needed or are
                # resolved/installed by anvil during installation in the first
                # place..
                if not utils.has_any(l.lower(), 'keystoneclient', 'oslo.config',
                                     'ldap', 'http://tarballs.openstack.org',
                                     'memcached')]

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        if self.get_bool_option('db-sync'):
            self._setup_db()
            self._sync_db()
        if self.get_bool_option('enable-pki'):
            self._setup_pki()

    def _sync_db(self):
        LOG.info("Syncing keystone to database: %s", colorizer.quote(DB_NAME))
        sync_cmd = MANAGE_CMD + ['db_sync']
        cmds = [{'cmd': sync_cmd, 'run_as_root': True}]
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
        to_set['SERVICE_ENDPOINT'] = params['endpoints']['admin']['uri']
        for (endpoint, details) in params['endpoints'].items():
            if endpoint.find('templated') != -1:
                continue
            to_set[("KEYSTONE_%s_URI" % (endpoint.upper()))] = details['uri']
        return to_set

    @property
    def config_files(self):
        return list(CONFIGS)

    def _setup_db(self):
        dbhelper.drop_db(distro=self.distro,
                         dbtype=self.get_option('db', 'type'),
                         dbname=DB_NAME,
                         **utils.merge_dicts(self.get_option('db'),
                                             dbhelper.get_shared_passwords(self)))
        dbhelper.create_db(distro=self.distro,
                           dbtype=self.get_option('db', 'type'),
                           dbname=DB_NAME,
                           **utils.merge_dicts(self.get_option('db'),
                                               dbhelper.get_shared_passwords(self)))

    def _setup_pki(self):
        LOG.info("Setting up keystone's pki support.")
        for value in PKI_FILES.values():
            sh.mkdirslist(sh.dirname(sh.joinpths(self.link_dir, value)),
                          tracewriter=self.tracewriter, adjust_suids=True)
        pki_cmd = MANAGE_CMD + ['pki_setup']
        cmds = [{'cmd': pki_cmd, 'run_as_root': True}]
        utils.execute_template(*cmds, cwd=self.bin_dir, params=self.config_params(None))

    def source_config(self, config_fn):
        real_fn = config_fn
        if config_fn == LOGGING_CONF:
            real_fn = 'logging.conf.sample'
        elif config_fn == ROOT_CONF:
            real_fn = "keystone.conf.sample"
        fn = sh.joinpths(self.get_option('app_dir'), 'etc', real_fn)
        return (fn, sh.load_file(fn))

    def _config_adjust_logging(self, contents, fn):
        with io.BytesIO(contents) as stream:
            config = cfg.create_parser(cfg.RewritableConfigParser, self)
            config.readfp(stream)
            config.set('logger_root', 'level', 'DEBUG')
            config.set('logger_root', 'handlers', "devel,production")
            contents = config.stringify(fn)
        return contents

    def _config_param_replace(self, config_fn, contents, parameters):
        if config_fn in [ROOT_CONF, LOGGING_CONF]:
            # We handle these ourselves
            return contents
        else:
            return comp.PythonInstallComponent._config_param_replace(self, config_fn, contents, parameters)

    def _config_adjust_root(self, contents, fn):
        params = khelper.get_shared_params(**utils.merge_dicts(self.options,
                                                               khelper.get_shared_passwords(self)))
        with io.BytesIO(contents) as stream:
            config = cfg.create_parser(cfg.RewritableConfigParser, self)
            config.readfp(stream)
            config.set('DEFAULT', 'admin_token', params['service_token'])
            config.set('DEFAULT', 'admin_port', params['endpoints']['admin']['port'])
            config.set('DEFAULT', 'public_port', params['endpoints']['public']['port'])
            config.set('DEFAULT', 'verbose', True)
            config.set('DEFAULT', 'debug', True)
            if self.get_bool_option('enable-pki'):
                config.set('signing', 'token_format', 'PKI')
                for (k, v) in PKI_FILES.items():
                    path = sh.joinpths(self.link_dir, v)
                    config.set('signing', k, path)
            else:
                config.set('signing', 'token_format', 'UUID')
            config.set('catalog', 'driver', 'keystone.catalog.backends.sql.Catalog')
            config.remove_option('DEFAULT', 'log_config')
            config.set('sql', 'connection', dbhelper.fetch_dbdsn(dbname=DB_NAME,
                                                                 utf8=True,
                                                                 dbtype=self.get_option('db', 'type'),
                                                                 **utils.merge_dicts(self.get_option('db'),
                                                                                     dbhelper.get_shared_passwords(self))))
            config.set('ec2', 'driver', "keystone.contrib.ec2.backends.sql.Ec2")
            contents = config.stringify(fn)
        return contents

    def _config_adjust(self, contents, name):
        if name == ROOT_CONF:
            return self._config_adjust_root(contents, name)
        elif name == LOGGING_CONF:
            return self._config_adjust_logging(contents, name)
        else:
            return contents

    def warm_configs(self):
        khelper.get_shared_passwords(self)

    def config_params(self, config_fn):
        # These be used to fill in the configuration params
        mp = comp.PythonInstallComponent.config_params(self, config_fn)
        mp['BIN_DIR'] = self.bin_dir
        mp['CONFIG_FILE'] = sh.joinpths(self.get_option('cfg_dir'), ROOT_CONF)
        return mp


class KeystoneRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.get_option('app_dir'), 'bin')
        self.init_fn = sh.joinpths(self.get_option('trace_dir'), INIT_WHAT_HAPPENED)

    def _filter_init(self, init_what):
        endpoints = init_what['endpoints']
        adjusted_endpoints = []
        # TODO(harlowja) make this better and based off of config...
        for endpoint in endpoints:
            if endpoint['service'] in ['swift', 'network']:
                continue
            else:
                adjusted_endpoints.append(endpoint)
        init_what['endpoints'] = adjusted_endpoints
        return init_what

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
            params['quantum'] = qhelper.get_shared_params(ip=self.get_option('ip'), **self.get_option('quantum'))
            params['cinder'] = chelper.get_shared_params(ip=self.get_option('ip'), **self.get_option('cinder'))
            wait_urls = [
                params['keystone']['endpoints']['admin']['uri'],
                params['keystone']['endpoints']['public']['uri'],
            ]
            for url in wait_urls:
                utils.wait_for_url(url)
            init_what = utils.load_yaml_text(contents)
            init_what = utils.expand_template_deep(self._filter_init(init_what), params)
            khelper.Initializer(params['keystone']['service_token'],
                                params['keystone']['endpoints']['admin']['uri']).initialize(**init_what)
            # Writing this makes sure that we don't init again
            sh.write_file(self.init_fn, utils.prettify_yaml(init_what))
            LOG.info("If you wish to re-run initialization, delete %s", colorizer.quote(self.init_fn))

    @property
    def applications(self):
        apps = []
        for (name, _values) in self.subsystems.items():
            name = "keystone-%s" % (name.lower())
            path = sh.joinpths(self.bin_dir, name)
            if sh.is_executable(path):
                apps.append(comp.Program(name, path, argv=self._fetch_argv(name)))
        return apps

    def _fetch_argv(self, name):
        return [
            '--config-file=%s' % (sh.joinpths('$CONFIG_DIR', ROOT_CONF)),
            "--debug",
            '--verbose',
            '--nouse-syslog',
            '--log-config=%s' % (sh.joinpths('$CONFIG_DIR', LOGGING_CONF)),
        ]


class KeystoneTester(comp.PythonTestingComponent):
    # Disable the keystone client integration tests
    def _get_test_command(self):
        base_cmd = comp.PythonTestingComponent._get_test_command(self)
        base_cmd = base_cmd + ['-xintegration']
        return base_cmd
