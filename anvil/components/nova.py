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
from anvil import exceptions
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

# This is a special marker file that when it exists, signifies that nova net was inited
NET_INITED_FN = 'nova.network.inited.yaml'

# This makes the database be in sync with nova
DB_SYNC_CMD = [
    {'cmd': ['$BIN_DIR/nova-manage', '--config-file', '$CFG_FILE', 'db', 'sync'], 'run_as_root': True},
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
        'cmd': ['$BIN_DIR/nova-manage', '--config-file', '$CFG_FILE', 'floating', 'create', '$FLOATING_RANGE'],
        'run_as_root': True,
    },
    {
        'cmd': ['$BIN_DIR/nova-manage', '--config-file', '$CFG_FILE',
                'floating', 'create', '--ip_range=$TEST_FLOATING_RANGE', '--pool=$TEST_FLOATING_POOL'],
        'run_as_root': True,
    },
]

# NCPU, NVOL, NAPI ... are here as possible subsystems of nova
NCPU = "cpu"
NVOL = "vol"
NAPI = "api"
NOBJ = "obj"
NNET = "net"
NCERT = "cert"
NSCHED = "sched"
NCAUTH = "cauth"
NXVNC = "xvnc"
NNOVNC = 'novnc'
SUBSYSTEMS = [NCPU, NVOL, NAPI,
              NOBJ, NNET, NCERT,
              NSCHED, NCAUTH, NXVNC,
              NNOVNC]

# What to start
APP_OPTIONS = {
    #these are currently the core components/applications
    'nova-api': ['--config-file', '$CFG_FILE'],
    'nova-compute': ['--config-file', '$CFG_FILE'],
    'nova-volume': ['--config-file', '$CFG_FILE'],
    'nova-network': ['--config-file', '$CFG_FILE'],
    'nova-scheduler': ['--config-file', '$CFG_FILE'],
    'nova-cert': ['--config-file', '$CFG_FILE'],
    'nova-objectstore': ['--config-file', '$CFG_FILE'],
    'nova-consoleauth': ['--config-file', '$CFG_FILE'],
    'nova-xvpvncproxy': ['--config-file', '$CFG_FILE'],
}

# Sub component names to actual app names (matching previous dict)
SUB_COMPONENT_NAME_MAP = {
    NCPU: 'nova-compute',
    NVOL: 'nova-volume',
    NAPI: 'nova-api',
    NOBJ: 'nova-objectstore',
    NNET: 'nova-network',
    NCERT: 'nova-cert',
    NSCHED: 'nova-scheduler',
    NCAUTH: 'nova-consoleauth',
    NXVNC: 'nova-xvpvncproxy',
}

# Subdirs of the checkout/download
BIN_DIR = 'bin'

# This is a special conf
CLEANER_DATA_CONF = 'nova-clean.sh'


class NovaUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)
        self.virsh = lv.Virsh(self.get_int_option('service_wait_seconds'), self.distro)

    def pre_uninstall(self):
        self._clear_libvirt_domains()
        self._clean_it()

    def _filter_subsystems(self):
        subs = set()
        for (name, _values) in self.subsystems.items():
            if name in SUB_COMPONENT_NAME_MAP:
                subs.add(name)
        return subs

    def _clean_it(self):
        cleaner_fn = sh.joinpths(self.get_option('app_dir'), BIN_DIR, CLEANER_DATA_CONF)
        if sh.isfile(cleaner_fn):
            LOG.info("Cleaning up your system by running nova cleaner script: %s", colorizer.quote(cleaner_fn))
            # These environment additions are important
            # in that they eventually affect how this script runs
            env = {
                'ENABLED_SERVICES': ",".join(self._filter_subsystems()),
            }
            sh.execute(cleaner_fn, run_as_root=True, env_overrides=env)

    def _clear_libvirt_domains(self):
        virt_driver = nhelper.canon_virt_driver(self.get_option('virt_driver'))
        if virt_driver == 'libvirt':
            inst_prefix = self.get_option('instance_name_prefix', 'instance-')
            libvirt_type = lv.canon_libvirt_type(self.get_option('libvirt_type'))
            self.virsh.clear_domains(libvirt_type, inst_prefix)


class NovaInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)
        self.conf_maker = nhelper.ConfConfigurator(self)

    @property
    def config_files(self):
        return list(CONFIGS)

    def _filter_pip_requires_line(self, line):
        if line.lower().find('quantumclient') != -1:
            return None
        if line.lower().find('glance') != -1:
            return None
        return line

    @property
    def env_exports(self):
        to_set = {}
        to_set['NOVA_VERSION'] = self.get_option('nova_version')
        to_set['COMPUTE_API_VERSION'] = self.get_option('nova_version')
        return to_set

    def verify(self):
        comp.PythonInstallComponent.verify(self)
        self.conf_maker.verify()

    def warm_configs(self):
        mq_type = nhelper.canon_mq_type(self.get_option('mq-type'))
        if mq_type == 'rabbit':
            rhelper.get_shared_passwords(self)

    def _sync_db(self):
        LOG.info("Syncing nova to database named: %s", colorizer.quote(DB_NAME))
        utils.execute_template(*DB_SYNC_CMD, params=self.config_params(None))

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        # Extra actions to do nova setup
        if self.get_bool_option('db-sync'):
            self._setup_db()
            self._sync_db()
        self._setup_cleaner()

    def _setup_cleaner(self):
        LOG.info("Configuring cleaner template: %s", colorizer.quote(CLEANER_DATA_CONF))
        (_fn, contents) = utils.load_template(self.name, CLEANER_DATA_CONF)
        # FIXME(harlowja), stop placing in checkout dir...
        cleaner_fn = sh.joinpths(sh.joinpths(self.get_option('app_dir'), BIN_DIR), CLEANER_DATA_CONF)
        sh.write_file(cleaner_fn, contents)
        sh.chmod(cleaner_fn, 0755)
        self.tracewriter.file_touched(cleaner_fn)

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
                                           **utils.merge_dicts(self.get_option('keystone'), 
                                                               khelper.get_shared_passwords(self)))
        
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

    def _config_adjust_logging(self, contents, fn):
        with io.BytesIO(contents) as stream:
            config = cfg.RewritableConfigParser()
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
        self.net_init_fn = sh.joinpths(self.get_option('trace_dir'), NET_INITED_FN)

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
                mp['FIXED_NETWORK_SIZE'] = self.get_option('fixed_network_size', default_value='256')
                mp['FIXED_RANGE'] = self.get_option('fixed_range', default_value='10.0.0.0/24')
                cmds.extend(FIXED_NET_CMDS)
            if self.get_bool_option('enable_floating'):
                # Create a floating network + test floating pool
                cmds.extend(FLOATING_NET_CMDS)
                mp['FLOATING_RANGE'] = self.get_option('floating_range', default_value='172.24.4.224/28')
                mp['TEST_FLOATING_RANGE'] = self.get_option('test_floating_range', default_value='192.168.253.0/29')
                mp['TEST_FLOATING_POOL'] = self.get_option('test_floating_pool', default_value='test')
            # Anything to run??
            if cmds:
                LOG.info("Creating your nova network to be used with instances.")
                utils.execute_template(*cmds, params=mp)
            # Writing this makes sure that we don't init again
            cmd_mp = {
                'cmds': cmds,
                'replacements': mp,
            }
            sh.write_file(ran_fn, utils.prettify_yaml(cmd_mp))
            LOG.info("If you wish to re-run network initialization, delete %s", colorizer.quote(ran_fn))

    def post_start(self):
        self._do_network_init()

    @property
    def apps_to_start(self):
        apps = []
        for (name, _values) in self.subsystems.items():
            if name in SUB_COMPONENT_NAME_MAP:
                apps.append({
                    'name': SUB_COMPONENT_NAME_MAP[name],
                    'path': sh.joinpths(self.get_option('app_dir'), BIN_DIR, SUB_COMPONENT_NAME_MAP[name]),
                })
        return apps

    def pre_start(self):
        # Let the parent class do its thing
        comp.PythonRuntime.pre_start(self)
        virt_driver = nhelper.canon_virt_driver(self.get_option('virt_driver'))
        if virt_driver == 'libvirt':
            virt_type = lv.canon_libvirt_type(self.get_option('libvirt_type'))
            LOG.info("Checking that your selected libvirt virtualization type %s is working and running.", colorizer.quote(virt_type))
            try:
                self.virsh.check_virt(virt_type)
                self.virsh.restart_service()
                LOG.info("Libvirt virtualization type %s seems to be working and running.", colorizer.quote(virt_type))
            except exceptions.ProcessExecutionError as e:
                msg = ("Libvirt type %r does not seem to be active or configured correctly, "
                        "perhaps you should be using %r instead: %s" %
                        (virt_type, lv.DEF_VIRT_TYPE, e))
                raise exceptions.StartException(msg)

    def app_params(self, app_name):
        params = comp.PythonRuntime.app_params(self, app_name)
        params['CFG_FILE'] = self.config_path
        return params

    def app_options(self, app):
        return APP_OPTIONS.get(app)


class NovaTester(comp.PythonTestingComponent):
    def _get_test_exclusions(self):
        return [
            # Disable since quantumclient is not always installed.
            'test_quantumv2',
        ]
