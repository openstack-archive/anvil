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
from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.components.helpers import db as dbhelper
from anvil.components.helpers import keystone as khelper
from anvil.components.helpers import nova as nhelper
from anvil.components.helpers import rabbit as rhelper
from anvil.components.helpers import virt as lv

LOG = logging.getLogger(__name__)

# Copies from helpers
API_CONF = nhelper.API_CONF
DB_NAME = nhelper.DB_NAME
PASTE_CONF = nhelper.PASTE_CONF

# Normal conf
POLICY_CONF = 'policy.json'
LOGGING_CONF = "logging.conf"
CONFIGS = [PASTE_CONF, POLICY_CONF, LOGGING_CONF, API_CONF]
ADJUST_CONFIGS = [PASTE_CONF]

# This is a special marker file that when it exists, signifies that nova
# net was inited
NET_INITED_FN = 'nova.network.inited.yaml'

# This makes the database be in sync with nova
DB_SYNC_CMD = [
    {'cmd': ['$BIN_DIR/nova-manage',
     '--config-file',
     '$CFG_FILE',
     'db',
     'sync'],
     'run_as_root': True},
]

# Used to create a fixed network when initializating nova
FIXED_NET_CMDS = [
    {
        'cmd': ['$BIN_DIR/nova-manage', '--config-file', '$CFG_FILE',
                'network', 'create', 'private', '$FIXED_RANGE', '1', '$FIXED_NETWORK_SIZE'],
        'run_as_root': True,
    },
]

# Used to create a floating network + test floating pool
FLOATING_NET_CMDS = [
    {
        'cmd': ['$BIN_DIR/nova-manage', '--config-file',
                '$CFG_FILE', 'floating', 'create', '$FLOATING_RANGE'],
        'run_as_root': True,
    },
    {
        'cmd': ['$BIN_DIR/nova-manage', '--config-file', '$CFG_FILE',
                'floating', 'create', '--ip_range=$TEST_FLOATING_RANGE', '--pool=$TEST_FLOATING_POOL'],
        'run_as_root': True,
    },
]

# Subdirs of the checkout/download
BIN_DIR = 'bin'


class NovaUninstaller(comp.PythonUninstallComponent):

    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)
        self.virsh = lv.Virsh(
            self.get_int_option(
                'service_wait_seconds'),
            self.distro)

    def pre_uninstall(self):
        if 'compute' in self.subsystems:
            self._clean_compute()
        if 'network' in self.subsystems:
            self._clean_net()

    def _clean_net(self):
        try:
            LOG.info("Cleaning up nova-network's dirty laundry.")
            cleaner = nhelper.NetworkCleaner(self)
            cleaner.clean()
        except Exception as e:
            LOG.warn(
                "Failed cleaning up nova-network's dirty laundry due to: %s",
                e)

    def _clean_compute(self):
        try:
            LOG.info("Cleaning up nova-compute's dirty laundry.")
            cleaner = nhelper.ComputeCleaner(self)
            cleaner.clean()
        except Exception as e:
            LOG.warn(
                "Failed cleaning up nova-compute's dirty laundry due to: %s",
                e)


class NovaInstaller(comp.PythonInstallComponent):

    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)
        self.conf_maker = nhelper.ConfConfigurator(self)

    @property
    def config_files(self):
        return list(CONFIGS)

    def _filter_pip_requires(self, fn, lines):
        return [l for l in lines
                # Take out entries that aren't really always needed or are
                # resolved/installed by anvil during installation in the first
                # place..
                if not utils.has_any(l.lower(), 'quantumclient',
                                     'cinder', 'glance', 'ldap', 'oslo.config',
                                     'keystoneclient')]

    @property
    def env_exports(self):
        to_set = utils.OrderedDict()
        to_set['OS_COMPUTE_API_VERSION'] = self.get_option('nova_version')
        n_params = nhelper.get_shared_params(**self.options)
        for (endpoint, details) in n_params['endpoints'].items():
            to_set[("NOVA_%s_URI" % (endpoint.upper()))] = details['uri']
        return to_set

    def verify(self):
        comp.PythonInstallComponent.verify(self)
        self.conf_maker.verify()

    def warm_configs(self):
        mq_type = nhelper.canon_mq_type(self.get_option('mq-type'))
        if mq_type == 'rabbit':
            rhelper.get_shared_passwords(self)

    def _sync_db(self):
        LOG.info(
            "Syncing nova to database named: %s",
            colorizer.quote(DB_NAME))
        utils.execute_template(*DB_SYNC_CMD, params=self.config_params(None))

    def _fix_virt(self):
        virt_driver = nhelper.canon_virt_driver(self.get_option('virt_driver'))
        if virt_driver == 'libvirt':
            virt_type = lv.canon_libvirt_type(self.get_option('libvirt_type'))
            if virt_type == 'qemu':
                # On RHEL it appears a sym-link needs to be created
                # to enable qemu to actually work, apparently fixed
                # in RHEL 6.4.
                #
                # See:
                # http://fedoraproject.org/wiki/Getting_started_with_OpenStack_EPEL
                if not sh.isfile('/usr/bin/qemu-system-x86_64'):
                    sh.symlink(
                        '/usr/libexec/qemu-kvm', '/usr/bin/qemu-system-x86_64',
                        tracewriter=self.tracewriter)

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        # Extra actions to do nova setup
        if self.get_bool_option('db-sync'):
            self._setup_db()
            self._sync_db()
        # Patch up your virtualization system
        self._fix_virt()

    def _setup_db(self):
        dbhelper.drop_db(distro=self.distro,
                         dbtype=self.get_option('db', 'type'),
                         dbname=DB_NAME,
                         **utils.merge_dicts(self.get_option('db'),
                                             dbhelper.get_shared_passwords(self)))
        # Explicitly use latin1: to avoid lp#829209, nova expects the database to
        # use latin1 by default, and then upgrades the database to utf8 (see the
        # 082_essex.py in nova)
        dbhelper.create_db(distro=self.distro,
                           dbtype=self.get_option('db', 'type'),
                           dbname=DB_NAME,
                           charset='latin1',
                           **utils.merge_dicts(self.get_option('db'),
                                               dbhelper.get_shared_passwords(self)))

    def _generate_nova_conf(self, fn):
        LOG.debug("Generating dynamic content for nova: %s.", (fn))
        return self.conf_maker.generate(fn)

    def source_config(self, config_fn):
        if config_fn == PASTE_CONF:
            config_fn = 'api-paste.ini'
        elif config_fn == LOGGING_CONF:
            config_fn = 'logging_sample.conf'
        elif config_fn == API_CONF:
            config_fn = 'nova.conf.sample'
        fn = sh.joinpths(self.get_option('app_dir'), 'etc', "nova", config_fn)
        return (fn, sh.load_file(fn))

    def _config_adjust_paste(self, contents, fn):
        params = khelper.get_shared_params(ip=self.get_option('ip'),
                                           service_user='nova',
                                           **utils.merge_dicts(
                                               self.get_option('keystone'),
                                           khelper.get_shared_passwords(self)))

        with io.BytesIO(contents) as stream:
            config = cfg.create_parser(cfg.RewritableConfigParser, self)
            config.readfp(stream)

            config.set(
                'filter:authtoken',
                'auth_host',
                params[
                    'endpoints'][
                        'admin'][
                            'host'])
            config.set(
                'filter:authtoken',
                'auth_port',
                params[
                    'endpoints'][
                        'admin'][
                            'port'])
            config.set(
                'filter:authtoken',
                'auth_protocol',
                params[
                    'endpoints'][
                        'admin'][
                            'protocol'])

            config.set(
                'filter:authtoken',
                'service_host',
                params[
                    'endpoints'][
                        'internal'][
                            'host'])
            config.set(
                'filter:authtoken',
                'service_port',
                params[
                    'endpoints'][
                        'internal'][
                            'port'])
            config.set(
                'filter:authtoken',
                'service_protocol',
                params[
                    'endpoints'][
                        'internal'][
                            'protocol'])

            config.set(
                'filter:authtoken',
                'admin_tenant_name',
                params[
                    'service_tenant'])
            config.set(
                'filter:authtoken',
                'admin_user',
                params[
                    'service_user'])
            config.set(
                'filter:authtoken',
                'admin_password',
                params[
                    'service_password'])

            contents = config.stringify(fn)
        return contents

    def _config_adjust_logging(self, contents, fn):
        with io.BytesIO(contents) as stream:
            config = cfg.create_parser(cfg.RewritableConfigParser, self)
            config.readfp(stream)
            config.set('logger_root', 'level', 'DEBUG')
            config.set('logger_root', 'handlers', "stdout")
            contents = config.stringify(fn)
        return contents

    def _config_adjust(self, contents, name):
        if name == PASTE_CONF:
            return self._config_adjust_paste(contents, name)
        elif name == LOGGING_CONF:
            return self._config_adjust_logging(contents, name)
        elif name == API_CONF:
            return self._generate_nova_conf(name)
        else:
            return contents

    def _config_param_replace(self, config_fn, contents, parameters):
        if config_fn in [PASTE_CONF, LOGGING_CONF, API_CONF]:
            # We handle these ourselves
            return contents
        else:
            return comp.PythonInstallComponent._config_param_replace(self, config_fn, contents, parameters)

    def config_params(self, config_fn):
        mp = comp.PythonInstallComponent.config_params(self, config_fn)
        mp['CFG_FILE'] = sh.joinpths(self.get_option('cfg_dir'), API_CONF)
        mp['BIN_DIR'] = sh.joinpths(self.get_option('app_dir'), BIN_DIR)
        return mp


class NovaRuntime(comp.PythonRuntime):

    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, *args, **kargs)
        self.wait_time = self.get_int_option('service_wait_seconds')
        self.virsh = lv.Virsh(self.wait_time, self.distro)
        self.config_path = sh.joinpths(self.get_option('cfg_dir'), API_CONF)
        self.bin_dir = sh.joinpths(self.get_option('app_dir'), BIN_DIR)
        self.net_init_fn = sh.joinpths(
            self.get_option('trace_dir'),
            NET_INITED_FN)

    def _do_network_init(self):
        ran_fn = self.net_init_fn
        if not sh.isfile(ran_fn) and self.get_bool_option('do-network-init'):
            # Figure out the commands to run
            cmds = []
            mp = {
                'CFG_FILE': self.config_path,
                'BIN_DIR': self.bin_dir
            }
            mp['BIN_DIR'] = self.bin_dir
            if self.get_bool_option('enable_fixed'):
                # Create a fixed network
                mp['FIXED_NETWORK_SIZE'] = self.get_option(
                    'fixed_network_size', default_value='256')
                mp['FIXED_RANGE'] = self.get_option(
                    'fixed_range',
                    default_value='10.0.0.0/24')
                cmds.extend(FIXED_NET_CMDS)
            if self.get_bool_option('enable_floating'):
                # Create a floating network + test floating pool
                cmds.extend(FLOATING_NET_CMDS)
                mp['FLOATING_RANGE'] = self.get_option(
                    'floating_range',
                    default_value='172.24.4.224/28')
                mp['TEST_FLOATING_RANGE'] = self.get_option(
                    'test_floating_range',
                    default_value='192.168.253.0/29')
                mp['TEST_FLOATING_POOL'] = self.get_option(
                    'test_floating_pool', default_value='test')
            # Anything to run??
            if cmds:
                LOG.info(
                    "Creating your nova network to be used with instances.")
                utils.execute_template(*cmds, params=mp)
            # Writing this makes sure that we don't init again
            cmd_mp = {
                'cmds': cmds,
                'replacements': mp,
            }
            sh.write_file(ran_fn, utils.prettify_yaml(cmd_mp))
            LOG.info(
                "If you wish to re-run network initialization, delete %s",
                colorizer.quote(ran_fn))

    def post_start(self):
        self._do_network_init()

    @property
    def applications(self):
        apps = []
        for (name, _values) in self.subsystems.items():
            name = "nova-%s" % (name.lower())
            path = sh.joinpths(self.bin_dir, name)
            if sh.is_executable(path):
                apps.append(
                    comp.Program(
                        name,
                        path,
                        argv=self._fetch_argv(
                            name)))
        return apps

    def pre_start(self):
        # Let the parent class do its thing
        comp.PythonRuntime.pre_start(self)
        virt_driver = nhelper.canon_virt_driver(self.get_option('virt_driver'))
        if virt_driver == 'libvirt':
            virt_type = lv.canon_libvirt_type(self.get_option('libvirt_type'))
            LOG.info(
                "Checking that your selected libvirt virtualization type %s is working and running.",
                colorizer.quote(virt_type))
            try:
                self.virsh.check_virt(virt_type)
                self.virsh.restart_service()
                LOG.info(
                    "Libvirt virtualization type %s seems to be working and running.",
                    colorizer.quote(virt_type))
            except excp.ProcessExecutionError as e:
                msg = ("Libvirt type %r does not seem to be active or configured correctly, "
                       "perhaps you should be using %r instead: %s" %
                      (virt_type, lv.DEF_VIRT_TYPE, e))
                raise excp.StartException(msg)

    def app_params(self, program):
        params = comp.PythonRuntime.app_params(self, program)
        params['CFG_FILE'] = self.config_path
        return params

    def _fetch_argv(self, name):
        return [
            '--config-file', '$CFG_FILE',
        ]
