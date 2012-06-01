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
from anvil import component as comp
from anvil import date
from anvil import exceptions
from anvil import libvirt as lv
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.helpers import db as dbhelper
from anvil.helpers import keystone as khelper
from anvil.helpers import nova as nhelper
from anvil.helpers import rabbit as rhelper

LOG = logging.getLogger(__name__)

# Copies from helpers
API_CONF = nhelper.API_CONF
DEF_VOL_PREFIX = nhelper.DEF_VOL_PREFIX
DEF_INSTANCE_PREFIX = nhelper.DEF_INSTANCE_PREFIX
DB_NAME = nhelper.DB_NAME

# Normal conf
PASTE_CONF = 'nova-api-paste.ini'
PASTE_SOURCE_FN = 'api-paste.ini'
POLICY_CONF = 'policy.json'
LOGGING_SOURCE_FN = 'logging_sample.conf'
LOGGING_CONF = "logging.conf"
CONFIGS = [PASTE_CONF, POLICY_CONF, LOGGING_CONF]
ADJUST_CONFIGS = [PASTE_CONF]

# This is a special marker file that when it exists, signifies that nova net was inited
NET_INITED_FN = 'nova.network.inited.yaml'

# This makes the database be in sync with nova
DB_SYNC_CMD = [
    {'cmd': ['%BIN_DIR%/nova-manage', '--config-file', '%CFG_FILE%', 'db', 'sync'], 'run_as_root': True},
]

# Used to create a fixed network when initializating nova
FIXED_NET_CMDS = [
    {
        'cmd': ['%BIN_DIR%/nova-manage', '--config-file', '%CFG_FILE%',
                'network', 'create', 'private', '%FIXED_RANGE%', '1', '%FIXED_NETWORK_SIZE%'],
        'run_as_root': True,
    },
]

# Used to create a floating network + test floating pool
FLOATING_NET_CMDS = [
    {
        'cmd': ['%BIN_DIR%/nova-manage', '--config-file', '%CFG_FILE%', 'floating', 'create', '%FLOATING_RANGE%'],
        'run_as_root': True,
    },
    {
        'cmd': ['%BIN_DIR%/nova-manage', '--config-file', '%CFG_FILE%',
                'floating', 'create', '--ip_range=%TEST_FLOATING_RANGE%', '--pool=%TEST_FLOATING_POOL%'],
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
SUBSYSTEMS = [NCPU, NVOL, NAPI,
    NOBJ, NNET, NCERT, NSCHED, NCAUTH, NXVNC]

# What to start
APP_OPTIONS = {
    #these are currently the core components/applications
    'nova-api': ['--config-file', '%CFG_FILE%'],
    'nova-compute': ['--config-file', '%CFG_FILE%'],
    'nova-volume': ['--config-file', '%CFG_FILE%'],
    'nova-network': ['--config-file', '%CFG_FILE%'],
    'nova-scheduler': ['--config-file', '%CFG_FILE%'],
    'nova-cert': ['--config-file', '%CFG_FILE%'],
    'nova-objectstore': ['--config-file', '%CFG_FILE%'],
    'nova-consoleauth': ['--config-file', '%CFG_FILE%'],
    'nova-xvpvncproxy': ['--config-file', '%CFG_FILE%'],
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

# Config keys we warm up so u won't be prompted later
WARMUP_PWS = [('rabbit', rhelper.PW_USER_PROMPT)]


class NovaMixin(object):

    def known_options(self):
        return set(['no-vnc', 'quantum', 'melange', 'no-db-sync'])

    def known_subsystems(self):
        return list(SUBSYSTEMS)

    def _get_config_files(self):
        return list(CONFIGS)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "nova_repo"),
            'branch': ("git", "nova_branch"),
        })
        return places


class NovaUninstaller(NovaMixin, comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.app_dir, BIN_DIR)
        self.virsh = lv.Virsh(self.cfg, self.distro)

    def pre_uninstall(self):
        self._clear_libvirt_domains()
        self._clean_it()

    def _clean_it(self):
        # These environment additions are important
        # in that they eventually affect how this script runs
        env = dict()
        env['ENABLED_SERVICES'] = ",".join(self.desired_subsystems)
        env['BIN_DIR'] = self.bin_dir
        env['VOLUME_NAME_PREFIX'] = self.cfg.getdefaulted('nova', 'volume_name_prefix', DEF_VOL_PREFIX)
        cleaner_fn = sh.joinpths(self.bin_dir, CLEANER_DATA_CONF)
        if sh.isfile(cleaner_fn):
            LOG.info("Cleaning up your system by running nova cleaner script: %s", colorizer.quote(cleaner_fn))
            cmd = [cleaner_fn]
            sh.execute(*cmd, run_as_root=True, env_overrides=env)

    def _clear_libvirt_domains(self):
        virt_driver = nhelper.canon_virt_driver(self.cfg.get('nova', 'virt_driver'))
        if virt_driver == 'libvirt':
            inst_prefix = self.cfg.getdefaulted('nova', 'instance_name_prefix', DEF_INSTANCE_PREFIX)
            libvirt_type = lv.canon_libvirt_type(self.cfg.get('nova', 'libvirt_type'))
            self.virsh.clear_domains(libvirt_type, inst_prefix)


class NovaInstaller(NovaMixin, comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.app_dir, BIN_DIR)
        self.paste_conf_fn = self._get_target_config_name(PASTE_CONF)
        self.volumes_enabled = False
        self.volume_configurator = None
        self.volumes_enabled = NVOL in self.desired_subsystems
        self.xvnc_enabled = NXVNC in self.desired_subsystems
        self.root_wrap_bin = sh.joinpths(self.distro.get_command_config('bin_dir'), 'nova-rootwrap')
        self.volume_maker = None
        if self.volumes_enabled:
            self.volume_maker = nhelper.VolumeConfigurator(self)
        self.conf_maker = nhelper.ConfConfigurator(self)

    def _get_symlinks(self):
        links = comp.PythonInstallComponent._get_symlinks(self)
        source_fn = sh.joinpths(self.cfg_dir, API_CONF)
        links[source_fn] = sh.joinpths(self._get_link_dir(), API_CONF)
        return links

    def verify(self):
        comp.PythonInstallComponent.verify(self)
        self.conf_maker.verify()
        if self.volume_maker:
            self.volume_maker.verify()

    def warm_configs(self):
        warm_pws = list(WARMUP_PWS)
        driver_canon = nhelper.canon_virt_driver(self.cfg.get('nova', 'virt_driver'))
        if driver_canon == 'xenserver':
            warm_pws.append(('xenapi_connection', 'the Xen API connection'))
        for pw_key, pw_prompt in warm_pws:
            self.cfg.get_password(pw_key, pw_prompt)

    def _sync_db(self):
        LOG.info("Syncing nova to database named: %s", colorizer.quote(DB_NAME))
        mp = self._get_param_map(None)
        utils.execute_template(*DB_SYNC_CMD, params=mp)

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        # Extra actions to do nova setup
        if 'no-db-sync' not in self.options:
            self._setup_db()
            self._sync_db()
        self._setup_cleaner()
        # Check if we need to do the vol subsystem
        if self.volume_maker:
            self.volume_maker.setup_volumes()

    def _setup_cleaner(self):
        LOG.info("Configuring cleaner template: %s", colorizer.quote(CLEANER_DATA_CONF))
        (_, contents) = utils.load_template(self.component_name, CLEANER_DATA_CONF)
        # FIXME, stop placing in checkout dir...
        tgt_fn = sh.joinpths(self.bin_dir, CLEANER_DATA_CONF)
        sh.write_file(tgt_fn, contents)
        sh.chmod(tgt_fn, 0755)
        self.tracewriter.file_touched(tgt_fn)

    def _setup_db(self):
        dbhelper.drop_db(self.cfg, self.distro, DB_NAME)
        dbhelper.create_db(self.cfg, self.distro, DB_NAME)

    def _generate_nova_conf(self, root_wrapped):
        conf_fn = self._get_target_config_name(API_CONF)
        LOG.info("Generating dynamic content for nova: %s.", colorizer.quote(conf_fn))
        nova_conf_contents = self.conf_maker.configure(root_wrapped)
        self.tracewriter.dirs_made(*sh.mkdirslist(sh.dirname(conf_fn)))
        self.tracewriter.cfg_file_written(sh.write_file(conf_fn, nova_conf_contents))

    def _get_source_config(self, config_fn):
        if config_fn == PASTE_CONF:
            config_fn = PASTE_SOURCE_FN
        elif config_fn == LOGGING_CONF:
            config_fn = LOGGING_SOURCE_FN
        fn = sh.joinpths(self.app_dir, 'etc', "nova", config_fn)
        return (fn, sh.load_file(fn))

    def _config_adjust_paste(self, contents, fn):
        params = khelper.get_shared_params(self.cfg, 'nova')
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
        else:
            return contents

    def _config_param_replace(self, config_fn, contents, parameters):
        if config_fn in [PASTE_CONF, LOGGING_CONF, API_CONF]:
            # We handle these ourselves
            return contents
        else:
            return comp.PythonInstallComponent._config_param_replace(self, config_fn, contents, parameters)

    def _get_param_map(self, config_fn):
        mp = comp.PythonInstallComponent._get_param_map(self, config_fn)
        mp['CFG_FILE'] = sh.joinpths(self.cfg_dir, API_CONF)
        mp['BIN_DIR'] = self.bin_dir
        return mp

    def _generate_root_wrap(self):
        if not self.cfg.getboolean('nova', 'do_root_wrap'):
            return False
        else:
            lines = list()
            lines.append("%s ALL=(root) NOPASSWD: %s" % (sh.getuser(), self.root_wrap_bin))
            fc = utils.joinlinesep(*lines)
            root_wrap_fn = sh.joinpths(self.distro.get_command_config('sudoers_dir'), 'nova-rootwrap')
            self.tracewriter.file_touched(root_wrap_fn)
            with sh.Rooted(True):
                sh.write_file(root_wrap_fn, fc)
                sh.chmod(root_wrap_fn, 0440)
                sh.chown(root_wrap_fn, sh.getuid(sh.ROOT_USER), sh.getgid(sh.ROOT_GROUP))
            return True

    def configure(self):
        configs_made = comp.PythonInstallComponent.configure(self)
        root_wrapped = self._generate_root_wrap()
        if root_wrapped:
            configs_made += 1
        self._generate_nova_conf(root_wrapped)
        configs_made += 1
        return configs_made


class NovaRuntime(NovaMixin, comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, *args, **kargs)
        self.bin_dir = sh.joinpths(self.app_dir, BIN_DIR)
        self.wait_time = max(self.cfg.getint('DEFAULT', 'service_wait_seconds'), 1)
        self.virsh = lv.Virsh(self.cfg, self.distro)
        self.net_enabled = NNET in self.desired_subsystems

    def _do_network_init(self):
        ran_fn = sh.joinpths(self.trace_dir, NET_INITED_FN)
        if not sh.isfile(ran_fn) and self.net_enabled:
            LOG.info("Creating your nova network to be used with instances.")
            # Figure out the commands to run
            mp = {}
            cmds = []
            mp['CFG_FILE'] = sh.joinpths(self.cfg_dir, API_CONF)
            mp['BIN_DIR'] = self.bin_dir
            if self.cfg.getboolean('nova', 'enable_fixed'):
                # Create a fixed network
                mp['FIXED_NETWORK_SIZE'] = self.cfg.getdefaulted('nova', 'fixed_network_size', '256')
                mp['FIXED_RANGE'] = self.cfg.getdefaulted('nova', 'fixed_range', '10.0.0.0/24')
                cmds.extend(FIXED_NET_CMDS)
            if 'quantum' not in self.options:
                if self.cfg.getboolean('nova', 'enable_floating'):
                    # Create a floating network + test floating pool
                    cmds.extend(FLOATING_NET_CMDS)
                    mp['FLOATING_RANGE'] = self.cfg.getdefaulted('nova', 'floating_range', '172.24.4.224/28')
                    mp['TEST_FLOATING_RANGE'] = self.cfg.getdefaulted('nova', 'test_floating_range', '192.168.253.0/29')
                    mp['TEST_FLOATING_POOL'] = self.cfg.getdefaulted('nova', 'test_floating_pool', 'test')
            else:
                LOG.info("Not creating floating IPs (not supported by quantum server)")
                LOG.info("Waiting %s seconds so that quantum can start up before running first time init." % (self.wait_time))
                sh.sleep(self.wait_time)
            # Anything to run??
            if cmds:
                utils.execute_template(*cmds, params=mp)
            # Writing this makes sure that we don't init again
            cmd_mp = {
                'cmds': cmds,
                'replacements': mp,
            }
            sh.write_file(ran_fn, utils.prettify_yaml(cmd_mp))
            LOG.info("If you wish to re-run initialization, delete %s", colorizer.quote(ran_fn))

    def post_start(self):
        self._do_network_init()

    def _get_apps_to_start(self):
        apps = list()
        for subsys in self.desired_subsystems:
            apps.append({
                'name': SUB_COMPONENT_NAME_MAP[subsys],
                'path': sh.joinpths(self.bin_dir, SUB_COMPONENT_NAME_MAP[subsys]),
            })
        return apps

    def pre_start(self):
        # Let the parent class do its thing
        comp.PythonRuntime.pre_start(self)
        virt_driver = nhelper.canon_virt_driver(self.cfg.get('nova', 'virt_driver'))
        if virt_driver == 'libvirt':
            # FIXME: The configuration for the virtualization-type
            # should come from the persona.
            virt_type = lv.canon_libvirt_type(self.cfg.get('nova', 'libvirt_type'))
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

    def _get_param_map(self, app_name):
        params = comp.PythonRuntime._get_param_map(self, app_name)
        params['CFG_FILE'] = sh.joinpths(self.cfg_dir, API_CONF)
        return params

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)
