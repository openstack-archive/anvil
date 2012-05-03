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
import os
import weakref

from urlparse import urlunparse

from anvil import cfg
from anvil import colorizer
from anvil import component as comp
from anvil import date
from anvil import exceptions
from anvil import libvirt as lv
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.components import db
from anvil.components import keystone
from anvil.components import rabbit

LOG = logging.getLogger(__name__)

# Special generated conf
API_CONF = 'nova.conf'

# How we reference some config files (in applications)
CFG_FILE_OPT = '--config-file'

# Normal conf
PASTE_CONF = 'nova-api-paste.ini'
PASTE_SOURCE_FN = 'api-paste.ini'
POLICY_CONF = 'policy.json'
LOGGING_SOURCE_FN = 'logging_sample.conf'
LOGGING_CONF = "logging.conf"
CONFIGS = [PASTE_CONF, POLICY_CONF, LOGGING_CONF]
ADJUST_CONFIGS = [PASTE_CONF]

# This is a special conf
NET_INIT_CONF = 'nova-network-init.sh'
NET_INIT_CMD_ROOT = [sh.joinpths("/", "bin", 'bash')]

# This db will be dropped then created
DB_NAME = 'nova'

# This makes the database be in sync with nova
DB_SYNC_CMD = [
    {'cmd': ['%BIN_DIR%/nova-manage', CFG_FILE_OPT, '%CFG_FILE%', 'db', 'sync']},
]

# These are used for nova volumes
VG_CHECK_CMD = [
    {'cmd': ['vgs', '%VOLUME_GROUP%'],
     'run_as_root': True}
]
VG_DEV_CMD = [
    {'cmd': ['losetup', '-f', '--show', '%VOLUME_BACKING_FILE%'],
     'run_as_root': True}
]
VG_CREATE_CMD = [
    {'cmd': ['vgcreate', '%VOLUME_GROUP%', '%DEV%'],
     'run_as_root': True}
]
VG_LVS_CMD = [
    {'cmd': ['lvs', '--noheadings', '-o', 'lv_name', '%VOLUME_GROUP%'],
     'run_as_root': True}
]
VG_LVREMOVE_CMD = [
    {'cmd': ['lvremove', '-f', '%VOLUME_GROUP%/%LV%'],
     'run_as_root': True}
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
    'nova-api': [CFG_FILE_OPT, '%CFG_FILE%'],
    'nova-compute': [CFG_FILE_OPT, '%CFG_FILE%'],
    'nova-volume': [CFG_FILE_OPT, '%CFG_FILE%'],
    'nova-network': [CFG_FILE_OPT, '%CFG_FILE%'],
    'nova-scheduler': [CFG_FILE_OPT, '%CFG_FILE%'],
    'nova-cert': [CFG_FILE_OPT, '%CFG_FILE%'],
    'nova-objectstore': [CFG_FILE_OPT, '%CFG_FILE%'],
    'nova-consoleauth': [CFG_FILE_OPT, '%CFG_FILE%'],
    'nova-xvpvncproxy': [CFG_FILE_OPT, '%CFG_FILE%'],
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

# Network class/driver/manager templs
QUANTUM_MANAGER = 'nova.network.quantum.manager.QuantumManager'
QUANTUM_IPAM_LIB = 'nova.network.quantum.melange_ipam_lib'
NET_MANAGER_TEMPLATE = 'nova.network.manager.%s'
FIRE_MANAGER_TEMPLATE = 'nova.virt.libvirt.firewall.%s'

# Sensible defaults
DEF_IMAGE_SERVICE = 'nova.image.glance.GlanceImageService'
DEF_SCHEDULER = 'nova.scheduler.filter_scheduler.FilterScheduler'
DEF_GLANCE_PORT = 9292
DEF_GLANCE_SERVER = "%s" + ":%s" % (DEF_GLANCE_PORT)
DEF_INSTANCE_PREFIX = 'instance-'
DEF_INSTANCE_TEMPL = DEF_INSTANCE_PREFIX + '%08x'
DEF_FIREWALL_DRIVER = 'IptablesFirewallDriver'
DEF_FLAT_VIRT_BRIDGE = 'br100'
DEF_NET_MANAGER = 'FlatDHCPManager'
DEF_VOL_PREFIX = 'volume-'
DEF_VOL_TEMPL = DEF_VOL_PREFIX + '%08x'

# Default virt types
DEF_VIRT_DRIVER = 'libvirt'

# Virt drivers map -> to there connection name
VIRT_DRIVER_CON_MAP = {
    'libvirt': 'libvirt',
    'xenserver': 'xenapi',
    'vmware': 'vmwareapi',
    'baremetal': 'baremetal',
}

# Only turned on if openvswitch enabled
QUANTUM_OPENSWITCH_OPS = {
    'libvirt_vif_type': 'ethernet',
    'libvirt_vif_driver': 'nova.virt.libvirt.vif.LibvirtOpenVswitchDriver',
    'linuxnet_interface_driver': 'nova.network.linux_net.LinuxOVSInterfaceDriver',
    'quantum_use_dhcp': True,
}

# This is a special conf
CLEANER_DATA_CONF = 'nova-clean.sh'
CLEANER_CMD_ROOT = [sh.joinpths("/", "bin", 'bash')]

# Xenserver specific defaults
XS_DEF_INTERFACE = 'eth1'
XA_CONNECTION_ADDR = '169.254.0.1'
XS_VNC_ADDR = XA_CONNECTION_ADDR
XS_DEF_BRIDGE = 'xapi1'
XA_CONNECTION_PORT = 80
XA_DEF_USER = 'root'
XA_DEF_CONNECTION_URL = urlunparse(('http', "%s:%s" % (XA_CONNECTION_ADDR, XA_CONNECTION_PORT), "", '', '', ''))

# Vnc specific defaults
VNC_DEF_ADDR = '127.0.0.1'

# Nova std compute extensions
STD_COMPUTE_EXTS = 'nova.api.openstack.compute.contrib.standard_extensions'

# Config keys we warm up so u won't be prompted later
WARMUP_PWS = [('rabbit', rabbit.PW_USER_PROMPT)]

# Nova conf default section
NV_CONF_DEF_SECTION = "[DEFAULT]"


def canon_virt_driver(virt_driver):
    if not virt_driver:
        return DEF_VIRT_DRIVER
    virt_driver = virt_driver.strip().lower()
    if not (virt_driver in VIRT_DRIVER_CON_MAP):
        return DEF_VIRT_DRIVER
    return virt_driver


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
            cmd = CLEANER_CMD_ROOT + [cleaner_fn]
            sh.execute(*cmd, run_as_root=True, env_overrides=env)

    def _clear_libvirt_domains(self):
        virt_driver = canon_virt_driver(self.cfg.get('nova', 'virt_driver'))
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
            self.volume_maker = NovaVolumeConfigurator(self)
        self.conf_maker = NovaConfConfigurator(self)

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
        driver_canon = canon_virt_driver(self.cfg.get('nova', 'virt_driver'))
        if driver_canon == 'xenserver':
            warm_pws.append(('xenapi_connection', 'the Xen API connection'))
        for pw_key, pw_prompt in warm_pws:
            self.pw_gen.get_password(pw_key, pw_prompt)

    def _setup_network_initer(self):
        LOG.info("Configuring nova network initializer template: %s", colorizer.quote(NET_INIT_CONF))
        (_, contents) = utils.load_template(self.component_name, NET_INIT_CONF)
        params = self._get_param_map(NET_INIT_CONF)
        contents = utils.param_replace(contents, params, True)
        # FIXME, stop placing in checkout dir...
        tgt_fn = sh.joinpths(self.bin_dir, NET_INIT_CONF)
        sh.write_file(tgt_fn, contents)
        sh.chmod(tgt_fn, 0755)
        self.tracewriter.file_touched(tgt_fn)

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
        if NNET in self.desired_subsystems:
            self._setup_network_initer()
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
        db.drop_db(self.cfg, self.pw_gen, self.distro, DB_NAME)
        db.create_db(self.cfg, self.pw_gen, self.distro, DB_NAME)

    def _generate_nova_conf(self, root_wrapped):
        conf_fn = self._get_target_config_name(API_CONF)
        LOG.info("Generating dynamic content for nova: %s", colorizer.quote(conf_fn))
        nova_conf_contents = self.conf_maker.configure(root_wrapped)
        self.tracewriter.dirs_made(*sh.mkdirslist(sh.dirname(conf_fn)))
        self.tracewriter.cfg_file_written(sh.write_file(conf_fn, nova_conf_contents))

    def _config_param_replace(self, config_fn, contents, parameters):
        if config_fn in [PASTE_CONF, LOGGING_CONF]:
            return contents
        else:
            return comp.PythonInstallComponent._config_param_replace(self, config_fn, contents, parameters)

    def _get_source_config(self, config_fn):
        if config_fn == PASTE_CONF:
            config_fn = PASTE_SOURCE_FN
        elif config_fn == LOGGING_CONF:
            config_fn = LOGGING_SOURCE_FN
        fn = sh.joinpths(self.app_dir, 'etc', "nova", config_fn)
        return (fn, sh.load_file(fn))

    def _config_adjust_paste(self, contents, fn):
        params = keystone.get_shared_params(self.cfg, self.pw_gen, 'nova')
        with io.BytesIO(contents) as stream:
            config = cfg.IgnoreMissingConfigParser()
            config.readfp(stream)
            config.set('filter:authtoken', 'auth_host', params['KEYSTONE_AUTH_HOST'])
            config.set('filter:authtoken', 'auth_port', params['KEYSTONE_AUTH_PORT'])
            config.set('filter:authtoken', 'auth_protocol', params['KEYSTONE_AUTH_PROTOCOL'])
            config.set('filter:authtoken', 'auth_uri', params['SERVICE_ENDPOINT'])
            config.set('filter:authtoken', 'admin_tenant_name', params['SERVICE_TENANT_NAME'])
            config.set('filter:authtoken', 'admin_user', params['SERVICE_USERNAME'])
            config.set('filter:authtoken', 'admin_password', params['SERVICE_PASSWORD'])
            config.set('filter:authtoken', 'service_host', params['KEYSTONE_SERVICE_HOST'])
            config.set('filter:authtoken', 'service_port', params['KEYSTONE_SERVICE_PORT'])
            config.set('filter:authtoken', 'service_protocol', params['KEYSTONE_SERVICE_PROTOCOL'])
            contents = config.stringify(fn)
        return contents

    def _config_adjust_logging(self, contents, fn):
        with io.BytesIO(contents) as stream:
            config = cfg.IgnoreMissingConfigParser()
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

    def _get_param_map(self, config_fn):
        mp = comp.PythonInstallComponent._get_param_map(self, config_fn)
        mp['CFG_FILE'] = sh.joinpths(self.cfg_dir, API_CONF)
        mp['BIN_DIR'] = self.bin_dir
        if config_fn == NET_INIT_CONF:
            mp['FLOATING_RANGE'] = self.cfg.getdefaulted('nova', 'floating_range', '172.24.4.224/28')
            mp['TEST_FLOATING_RANGE'] = self.cfg.getdefaulted('nova', 'test_floating_range', '192.168.253.0/29')
            mp['TEST_FLOATING_POOL'] = self.cfg.getdefaulted('nova', 'test_floating_pool', 'test')
            mp['FIXED_NETWORK_SIZE'] = self.cfg.getdefaulted('nova', 'fixed_network_size', '256')
            mp['FIXED_RANGE'] = self.cfg.getdefaulted('nova', 'fixed_range', '10.0.0.0/24')
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

    def _setup_network_init(self):
        tgt_fn = sh.joinpths(self.bin_dir, NET_INIT_CONF)
        if sh.is_executable(tgt_fn):
            LOG.info("Creating your nova network to be used with instances.")
            # If still there, run it
            # these environment additions are important
            # in that they eventually affect how this script runs
            if 'quantum' in self.options:
                LOG.info("Waiting %s seconds so that quantum can start up before running first time init." % (self.wait_time))
                sh.sleep(self.wait_time)
            env = dict()
            env['ENABLED_SERVICES'] = ",".join(self.options)
            setup_cmd = NET_INIT_CMD_ROOT + [tgt_fn]
            LOG.info("Running %s command to initialize nova's network.", colorizer.quote(" ".join(setup_cmd)))
            sh.execute(*setup_cmd, env_overrides=env, run_as_root=False)
            utils.mark_unexecute_file(tgt_fn, env)

    def post_start(self):
        self._setup_network_init()

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
        virt_driver = canon_virt_driver(self.cfg.get('nova', 'virt_driver'))
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


# This will configure nova volumes which in a developer box
# is a volume group (lvm) that are backed by a loopback file
class NovaVolumeConfigurator(object):
    def __init__(self, installer):
        self.installer = weakref.proxy(installer)
        self.cfg = installer.cfg
        self.app_dir = installer.app_dir
        self.distro = installer.distro

    def setup_volumes(self):
        self._setup_vol_groups()

    def verify(self):
        pass

    def _setup_vol_groups(self):
        LOG.info("Attempting to setup volume groups for nova volume management.")
        mp = dict()
        backing_file = self.cfg.getdefaulted('nova', 'volume_backing_file', sh.joinpths(self.app_dir, 'nova-volumes-backing-file'))
        vol_group = self.cfg.getdefaulted('nova', 'volume_group', 'nova-volumes')
        backing_file_size = utils.to_bytes(self.cfg.getdefaulted('nova', 'volume_backing_file_size', '2052M'))
        mp['VOLUME_GROUP'] = vol_group
        mp['VOLUME_BACKING_FILE'] = backing_file
        mp['VOLUME_BACKING_FILE_SIZE'] = backing_file_size
        try:
            utils.execute_template(*VG_CHECK_CMD, params=mp)
            LOG.warn("Volume group already exists: %r" % (vol_group))
        except exceptions.ProcessExecutionError as err:
            # Check that the error from VG_CHECK is an expected error
            if err.exit_code != 5:
                raise
            LOG.info("Need to create volume group: %r" % (vol_group))
            sh.touch_file(backing_file, die_if_there=False, file_size=backing_file_size)
            vg_dev_result = utils.execute_template(*VG_DEV_CMD, params=mp)
            if vg_dev_result and vg_dev_result[0]:
                LOG.debug("VG dev result: %s" % (vg_dev_result))
                # Strip the newlines out of the stdout (which is in the first
                # element of the first (and only) tuple in the response
                (sysout, _) = vg_dev_result[0]
                mp['DEV'] = sysout.replace('\n', '')
                utils.execute_template(*VG_CREATE_CMD, params=mp)
        # One way or another, we should have the volume group, Now check the
        # logical volumes
        self._process_lvs(mp)
        # Finish off by restarting tgt, and ignore any errors
        cmdrestart = self.distro.get_command('iscsi', 'restart', quiet=True)
        if cmdrestart:
            sh.execute(*cmdrestart, run_as_root=True, check_exit_code=False)

    def _process_lvs(self, mp):
        LOG.info("Attempting to setup logical volumes for nova volume management.")
        lvs_result = utils.execute_template(*VG_LVS_CMD, params=mp)
        if lvs_result and lvs_result[0]:
            vol_name_prefix = self.cfg.getdefaulted('nova', 'volume_name_prefix', DEF_VOL_PREFIX)
            LOG.debug("Using volume name prefix: %r" % (vol_name_prefix))
            (sysout, _) = lvs_result[0]
            for stdout_line in sysout.split('\n'):
                stdout_line = stdout_line.strip()
                if stdout_line:
                    # Ignore blank lines
                    LOG.debug("Processing LVS output line: %r" % (stdout_line))
                    if stdout_line.startswith(vol_name_prefix):
                        # TODO still need to implement the following:
                        # tid=`egrep "^tid.+$lv" /proc/net/iet/volume | cut -f1 -d' ' | tr ':' '='`
                        # if [[ -n "$tid" ]]; then
                        #   lun=`egrep "lun.+$lv" /proc/net/iet/volume | cut -f1 -d' ' | tr ':' '=' | tr -d '\t'`
                        #   sudo ietadm --op delete --$tid --$lun
                        # fi
                        # sudo lvremove -f $VOLUME_GROUP/$lv
                        raise NotImplementedError("LVS magic not yet implemented!")
                    mp['LV'] = stdout_line
                    utils.execute_template(*VG_LVREMOVE_CMD, params=mp)


# This class has the smarts to build the configuration file based on
# various runtime values. A useful reference for figuring out this
# is at http://docs.openstack.org/diablo/openstack-compute/admin/content/ch_configuring-openstack-compute.html
# See also: https://github.com/openstack/nova/blob/master/etc/nova/nova.conf.sample
class NovaConfConfigurator(object):
    def __init__(self, installer):
        self.installer = weakref.proxy(installer)
        self.cfg = installer.cfg
        self.pw_gen = installer.pw_gen
        self.instances = installer.instances
        self.component_dir = installer.component_dir
        self.app_dir = installer.app_dir
        self.tracewriter = installer.tracewriter
        self.paste_conf_fn = installer.paste_conf_fn
        self.distro = installer.distro
        self.cfg_dir = installer.cfg_dir
        self.options = installer.options
        self.xvnc_enabled = installer.xvnc_enabled
        self.volumes_enabled = installer.volumes_enabled
        self.novnc_enabled = 'no-vnc' in installer.options

    def _getbool(self, name):
        return self.cfg.getboolean('nova', name)

    def _getstr(self, name, default=''):
        return self.cfg.getdefaulted('nova', name, default)

    def verify(self):
        # Do a little check to make sure actually have that interface/s
        public_interface = self._getstr('public_interface')
        vlan_interface = self._getstr('vlan_interface', public_interface)
        known_interfaces = utils.get_interfaces()
        if not public_interface in known_interfaces:
            msg = "Public interface %r is not a known interface (is it one of %s??)" % (public_interface, ", ".join(known_interfaces))
            raise exceptions.ConfigException(msg)
        if not vlan_interface in known_interfaces:
            msg = "VLAN interface %r is not a known interface (is it one of %s??)" % (vlan_interface, ", ".join(known_interfaces))
            raise exceptions.ConfigException(msg)
        # Driver specific interface checks
        drive_canon = canon_virt_driver(self._getstr('virt_driver'))
        if drive_canon == 'xenserver':
            xs_flat_ifc = self._getstr('xs_flat_interface', XS_DEF_INTERFACE)
            if xs_flat_ifc and not xs_flat_ifc in known_interfaces:
                msg = "Xenserver flat interface %s is not a known interface (is it one of %s??)" % (xs_flat_ifc, ", ".join(known_interfaces))
                raise exceptions.ConfigException(msg)
        elif drive_canon == 'libvirt':
            flat_interface = self._getstr('flat_interface')
            if flat_interface and not flat_interface in known_interfaces:
                msg = "Libvirt flat interface %s is not a known interface (is it one of %s??)" % (flat_interface, ", ".join(known_interfaces))
                raise exceptions.ConfigException(msg)

    def configure(self, root_wrapped):
        # Everything built goes in here
        nova_conf = NovaConf()

        # Used more than once so we calculate it ahead of time
        hostip = self.cfg.get('host', 'ip')

        if self._getbool('verbose'):
            nova_conf.add('verbose', True)

        # Check if we have a logdir specified. If we do, we'll make
        # sure that it exists. We will *not* use tracewrite because we
        # don't want to lose the logs when we uninstall
        logdir = self._getstr('logdir')
        if logdir:
            full_logdir = sh.abspth(logdir)
            nova_conf.add('logdir', full_logdir)
            # Will need to be root to create it since it may be in /var/log
            if not sh.isdir(full_logdir):
                LOG.debug("Making sure that nova logdir exists at: %s" % full_logdir)
                with sh.Rooted(True):
                    sh.mkdir(full_logdir)
                    sh.chmod(full_logdir, 0777)

        # Allow the admin api?
        if self._getbool('allow_admin_api'):
            nova_conf.add('allow_admin_api', True)

        # FIXME: ??
        nova_conf.add('allow_resize_to_same_host', True)

        # Which scheduler do u want?
        nova_conf.add('compute_scheduler_driver', self._getstr('scheduler', DEF_SCHEDULER))

        # Rate limit the api??
        if self._getbool('api_rate_limit'):
            nova_conf.add('api_rate_limit', str(True))
        else:
            nova_conf.add('api_rate_limit', str(False))

        # Setup any network settings
        self._configure_network_settings(nova_conf)

        # Setup nova volume settings
        if self.volumes_enabled:
            self._configure_vols(nova_conf)

        # The ip of where we are running
        nova_conf.add('my_ip', hostip)

        # Setup your sql connection
        nova_conf.add('sql_connection', db.fetch_dbdsn(self.cfg, self.pw_gen, DB_NAME))

        # Configure anything libvirt related?
        virt_driver = canon_virt_driver(self._getstr('virt_driver'))
        if virt_driver == 'libvirt':
            libvirt_type = lv.canon_libvirt_type(self._getstr('libvirt_type'))
            self._configure_libvirt(libvirt_type, nova_conf)

        # How instances will be presented
        instance_template = self._getstr('instance_name_prefix') + self._getstr('instance_name_postfix')
        if not instance_template:
            instance_template = DEF_INSTANCE_TEMPL
        nova_conf.add('instance_name_template', instance_template)

        # Enable the standard extensions
        nova_conf.add('osapi_compute_extension', STD_COMPUTE_EXTS)

        # Auth will be using keystone
        nova_conf.add('auth_strategy', 'keystone')

        # Vnc settings setup
        self._configure_vnc(nova_conf)

        # Where our paste config is
        nova_conf.add('api_paste_config', self.paste_conf_fn)

        # What our imaging service will be
        self._configure_image_service(nova_conf, hostip)

        # Configs for ec2 / s3 stuff
        nova_conf.add('ec2_dmz_host', self._getstr('ec2_dmz_host', hostip))
        nova_conf.add('s3_host', hostip)

        # How is your rabbit setup?
        nova_conf.add('rabbit_host', self.cfg.getdefaulted('rabbit', 'rabbit_host', hostip))
        nova_conf.add('rabbit_password', self.cfg.get("passwords", "rabbit"))

        # Where instances will be stored
        instances_path = self._getstr('instances_path', sh.joinpths(self.component_dir, 'instances'))
        self._configure_instances_path(instances_path, nova_conf)

        # Is this a multihost setup?
        self._configure_multihost(nova_conf)

        # Handle any virt driver specifics
        self._configure_virt_driver(nova_conf)

        # Setup our root wrap helper that will limit our sudo ability
        if root_wrapped:
            self._configure_root_wrap(nova_conf)

        # Annnnnd extract to finish
        return self._get_content(nova_conf)

    def _get_extra(self, key):
        extras = self._getstr(key)
        cleaned_lines = list()
        extra_lines = extras.splitlines()
        for line in extra_lines:
            cleaned_line = line.strip()
            if len(cleaned_line):
                cleaned_lines.append(cleaned_line)
        return cleaned_lines

    def _convert_extra_flags(self, extra_flags):
        converted_flags = list()
        for f in extra_flags:
            cleaned_opt = f.lstrip("-")
            if len(cleaned_opt) == 0:
                continue
            if cleaned_opt.find("=") == -1:
                cleaned_opt += "=%s" % (True)
            converted_flags.append(cleaned_opt)
        return converted_flags

    def _get_content(self, nova_conf):
        generated_content = nova_conf.generate()
        extra_flags = self._get_extra('extra_flags')
        if extra_flags:
            LOG.warning("EXTRA_FLAGS is defined and may need to be converted to EXTRA_OPTS!")
            extra_flags = self._convert_extra_flags(extra_flags)
        extra_opts = self._get_extra('extra_opts')
        if extra_flags or extra_opts:
            new_contents = list()
            new_contents.append(generated_content)
            new_contents.append("")
            new_contents.append("# Extra flags")
            new_contents.append("")
            new_contents.extend(extra_flags)
            new_contents.append("")
            new_contents.append("# Extra options")
            new_contents.append("")
            new_contents.extend(extra_opts)
            new_contents.append("")
            generated_content = utils.joinlinesep(*new_contents)
        return generated_content

    def _configure_root_wrap(self, nova_conf):
        nova_conf.add('root_helper', 'sudo %s' % (self.installer.root_wrap_bin))

    def _configure_image_service(self, nova_conf, hostip):
        # What image service we will u be using sir?
        img_service = self._getstr('img_service', DEF_IMAGE_SERVICE)
        nova_conf.add('image_service', img_service)

        # If glance then where is it?
        if img_service.lower().find("glance") != -1:
            glance_api_server = self._getstr('glance_server', (DEF_GLANCE_SERVER % (hostip)))
            nova_conf.add('glance_api_servers', glance_api_server)

    def _configure_vnc(self, nova_conf):
        if self.novnc_enabled:
            nova_conf.add('novncproxy_base_url', self._getstr('vncproxy_url'))

        if self.xvnc_enabled:
            nova_conf.add('xvpvncproxy_base_url', self._getstr('xvpvncproxy_url'))

        nova_conf.add('vncserver_listen', self._getstr('vncserver_listen', VNC_DEF_ADDR))

        # If no vnc proxy address was specified,
        # pick a default based on which
        # driver we're using.
        vncserver_proxyclient_address = self._getstr('vncserver_proxyclient_address')
        if not vncserver_proxyclient_address:
            drive_canon = canon_virt_driver(self._getstr('virt_driver'))
            if drive_canon == 'xenserver':
                vncserver_proxyclient_address = XS_VNC_ADDR
            else:
                vncserver_proxyclient_address = VNC_DEF_ADDR

        nova_conf.add('vncserver_proxyclient_address', vncserver_proxyclient_address)

    def _configure_vols(self, nova_conf):
        nova_conf.add('volume_group', self._getstr('volume_group'))
        vol_name_tpl = self._getstr('volume_name_prefix') + self._getstr('volume_name_postfix')
        if not vol_name_tpl:
            vol_name_tpl = DEF_VOL_TEMPL
        nova_conf.add('volume_name_template', vol_name_tpl)
        nova_conf.add('iscsi_helper', 'tgtadm')

    def _configure_network_settings(self, nova_conf):
        # TODO this might not be right....
        if 'quantum' in self.options:
            nova_conf.add('network_manager', QUANTUM_MANAGER)
            hostip = self.cfg.get('host', 'ip')
            nova_conf.add('quantum_connection_host', self.cfg.getdefaulted('quantum', 'q_host', hostip))
            nova_conf.add('quantum_connection_port', self.cfg.getdefaulted('quantum', 'q_port', '9696'))
            if self.cfg.get('quantum', 'q_plugin') == 'openvswitch':
                for (key, value) in QUANTUM_OPENSWITCH_OPS.items():
                    nova_conf.add(key, value)
            if 'melange' in self.options:
                nova_conf.add('quantum_ipam_lib', QUANTUM_IPAM_LIB)
                nova_conf.add('use_melange_mac_generation', True)
                nova_conf.add('melange_host', self.cfg.getdefaulted('melange', 'm_host', hostip))
                nova_conf.add('melange_port', self.cfg.getdefaulted('melange', 'm_port', '9898'))
        else:
            nova_conf.add('network_manager', NET_MANAGER_TEMPLATE % (self._getstr('network_manager', DEF_NET_MANAGER)))

        # Configs dhcp bridge stuff???
        # TODO: why is this the same as the nova.conf?
        nova_conf.add('dhcpbridge_flagfile', sh.joinpths(self.cfg_dir, API_CONF))

        # Network prefix for the IP network that all the projects for future VM guests reside on. Example: 192.168.0.0/12
        nova_conf.add('fixed_range', self._getstr('fixed_range'))

        # The value for vlan_interface may default to the the current value
        # of public_interface. We'll grab the value and keep it handy.
        public_interface = self._getstr('public_interface')
        vlan_interface = self._getstr('vlan_interface', public_interface)
        nova_conf.add('public_interface', public_interface)
        nova_conf.add('vlan_interface', vlan_interface)

        # This forces dnsmasq to update its leases table when an instance is terminated.
        nova_conf.add('force_dhcp_release', True)

    def _configure_multihost(self, nova_conf):
        if self._getbool('multi_host'):
            nova_conf.add('multi_host', True)
            nova_conf.add('send_arp_for_ha', True)

    def _configure_instances_path(self, instances_path, nova_conf):
        nova_conf.add('instances_path', instances_path)
        LOG.debug("Attempting to create instance directory: %r", instances_path)
        self.tracewriter.dirs_made(*sh.mkdirslist(instances_path))
        LOG.debug("Adjusting permissions of instance directory: %r", instances_path)
        sh.chmod(instances_path, 0777)
        instance_parent = sh.dirname(instances_path)
        LOG.debug("Adjusting permissions of instance directory parent: %r", instance_parent)
        # In cases where you are using kvm + qemu
        # On certain distros (ie RHEL) this user needs to be able
        # To enter the parents of the instance path, if this is in /home/BLAH/ then
        # Without enabling the whole path, this user can't write there. This helps fix that...
        with sh.Rooted(True):
            for p in sh.explode_path(instance_parent):
                if not os.access(p, os.X_OK) and sh.isdir(p):
                    # Need to be able to go into that directory
                    sh.chmod(p, os.stat(p).st_mode | 0755)

    def _configure_libvirt(self, virt_type, nova_conf):
        if virt_type == 'lxc':
            #TODO need to add some goodies here
            pass
        nova_conf.add('libvirt_type', virt_type)

    # Configures any virt driver settings
    def _configure_virt_driver(self, nova_conf):
        drive_canon = canon_virt_driver(self._getstr('virt_driver'))
        nova_conf.add('connection_type', VIRT_DRIVER_CON_MAP.get(drive_canon, drive_canon))
        # Special driver settings
        if drive_canon == 'xenserver':
            nova_conf.add('xenapi_connection_url', self._getstr('xa_connection_url', XA_DEF_CONNECTION_URL))
            nova_conf.add('xenapi_connection_username', self._getstr('xa_connection_username', XA_DEF_USER))
            nova_conf.add('xenapi_connection_password', self.cfg.get("passwords", "xenapi_connection"))
            nova_conf.add('noflat_injected', True)
            nova_conf.add('firewall_driver', FIRE_MANAGER_TEMPLATE % (self._getstr('xs_firewall_driver', DEF_FIREWALL_DRIVER)))
            nova_conf.add('flat_network_bridge', self._getstr('xs_flat_network_bridge', XS_DEF_BRIDGE))
            xs_flat_ifc = self._getstr('xs_flat_interface', XS_DEF_INTERFACE)
            if xs_flat_ifc:
                nova_conf.add('flat_interface', xs_flat_ifc)
        elif drive_canon == 'libvirt':
            nova_conf.add('firewall_driver', FIRE_MANAGER_TEMPLATE % (self._getstr('libvirt_firewall_driver', DEF_FIREWALL_DRIVER)))
            nova_conf.add('flat_network_bridge', self._getstr('flat_network_bridge', DEF_FLAT_VIRT_BRIDGE))
            flat_interface = self._getstr('flat_interface')
            if flat_interface:
                nova_conf.add('flat_interface', flat_interface)


# This class represents the data/format of the nova config file
class NovaConf(object):
    def __init__(self):
        self.lines = list()

    def add(self, key, value, *values):
        if not key:
            raise exceptions.BadParamException("Can not add a empty/none/false key")
        real_key = str(key)
        real_value = ""
        if len(values):
            str_values = [str(value)] + [str(v) for v in values]
            real_value = ",".join(str_values)
        else:
            real_value = str(value)
        self.lines.append({'key': real_key, 'value': real_value})
        LOG.debug("Added nova conf key %r with value %r" % (real_key, real_value))

    def _form_entry(self, key, value, params=None):
        real_value = utils.param_replace(str(value), params)
        entry = "%s=%s" % (key, real_value)
        return entry

    def _generate_header(self):
        lines = list()
        lines.append("# Generated on %s by (%s)" % (date.rcf8222date(), sh.getuser()))
        lines.append("")
        lines.append(NV_CONF_DEF_SECTION)
        lines.append("")
        return lines

    def _generate_footer(self):
        return list()

    def generate(self, param_dict=None):
        lines = list()
        lines.extend(self._generate_header())
        lines.extend(sorted(self._generate_lines(param_dict)))
        lines.extend(self._generate_footer())
        return utils.joinlinesep(*lines)

    def _generate_lines(self, params=None):
        lines = list()
        for line_entry in self.lines:
            key = line_entry.get('key')
            value = line_entry.get('value')
            lines.append(self._form_entry(key, value, params))
        return lines
