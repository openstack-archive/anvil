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
import stat

from devstack import cfg
from devstack import component as comp
from devstack import exceptions
from devstack import libvirt as virsh
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

from devstack.components import db
from devstack.components import keystone


#id
TYPE = settings.NOVA
LOG = logging.getLogger('devstack.components.nova')

#special generatedconf
API_CONF = 'nova.conf'

#normal conf
PASTE_CONF = 'nova-api-paste.ini'
CONFIGS = [PASTE_CONF]

#this db will be dropped then created
DB_NAME = 'nova'

#this makes the database be in sync with nova
DB_SYNC_CMD = [
    {'cmd': ['%BINDIR%/nova-manage', '--flagfile', '%CFGFILE%',
             'db', 'sync']},
]

#these setup your dev network
NETWORK_SETUP_CMDS = [
    #this always happens (even in quantum mode)
    {'cmd': ['%BINDIR%/nova-manage', '--flagfile', '%CFGFILE%',
              'network', 'create', 'private', '%FIXED_RANGE%', 1, '%FIXED_NETWORK_SIZE%']},
    #these only happen if not in quantum mode
    {'cmd': ['%BINDIR%/nova-manage', '--flagfile', '%CFGFILE%',
              'floating', 'create', '%FLOATING_RANGE%']},
    {'cmd': ['%BINDIR%/nova-manage', '--flagfile', '%CFGFILE%',
              'floating', 'create', '--ip_range=%TEST_FLOATING_RANGE%',
              '--pool=%TEST_FLOATING_POOL%']}
]

#these are used for nova volumens
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
RESTART_TGT_CMD = [
    {'cmd': ['stop', 'tgt'], 'run_as_root': True},
    {'cmd': ['start', 'tgt'], 'run_as_root': True}
]

# NCPU, NVOL, NAPI ... are here as possible subcomponents of nova
NCPU = "cpu"
NVOL = "vol"
NAPI = "api"
NOBJ = "obj"
NNET = "net"
NCERT = "cert"
NSCHED = "sched"
NCAUTH = "cauth"
NXVNC = "xvnc"
SUBCOMPONENTS = [NCPU, NVOL, NAPI,
    NOBJ, NNET, NCERT, NSCHED, NCAUTH, NXVNC]

#the pkg json files nova requires for installation
REQ_PKGS = ['general.json', 'nova.json']

# Additional packages for subcomponents
ADD_PKGS = {
    NAPI:
        [
            'n-api.json',
        ],
    NCPU:
        [
            'n-cpu.json',
        ],
    NVOL:
        [
            'n-vol.json',
        ],
}

# Adjustments to nova paste pipeline for keystone
PASTE_PIPELINE_KEYSTONE_ADJUST = {
    'pipeline:ec2cloud': {'pipeline': 'ec2faultwrap logrequest totoken authtoken keystonecontext cloudrequest authorizer ec2executor'},
    'pipeline:ec2admin': {'pipeline': "ec2faultwrap logrequest totoken authtoken keystonecontext adminrequest authorizer ec2executor"},
    'pipeline:openstack_compute_api_v2': {'pipeline': "faultwrap authtoken keystonecontext ratelimit osapi_compute_app_v2"},
    'pipeline:openstack_volume_api_v1': {'pipeline': "faultwrap authtoken keystonecontext ratelimit osapi_volume_app_v1"},
    'pipeline:openstack_api_v2': {'pipeline': 'faultwrap authtoken keystonecontext ratelimit osapi_app_v2'},
}

# What to start
APP_OPTIONS = {
    #these are currently the core components/applications
    'nova-api': ['--flagfile', '%CFGFILE%'],
    'nova-compute': ['--flagfile', '%CFGFILE%'],
    'nova-volume': ['--flagfile', '%CFGFILE%'],
    'nova-network': ['--flagfile', '%CFGFILE%'],
    'nova-scheduler': ['--flagfile', '%CFGFILE%'],
    'nova-cert': ['--flagfile', '%CFGFILE%'],
    'nova-objectstore': ['--flagfile', '%CFGFILE%'],
    'nova-consoleauth': [],
    'nova-xvpvncproxy': ['--flagfile', '%CFGFILE%'],
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

#subdirs of the checkout/download
BIN_DIR = 'bin'
CONFIG_DIR = "etc"

#These are used by NovaConf
QUANTUM_MANAGER = 'nova.network.quantum.manager.QuantumManager'
NET_MANAGER_TEMPLATE = 'nova.network.manager.%s'
DEF_IMAGE_SERVICE = 'nova.image.glance.GlanceImageService'
DEF_SCHEDULER = 'nova.scheduler.simple.SimpleScheduler'
DEF_GLANCE_PORT = 9292

#only turned on if vswitch enabled
QUANTUM_OPENSWITCH_OPS = {
    'libvirt_vif_type': 'ethernet',
    'libvirt_vif_driver': 'nova.virt.libvirt.vif.LibvirtOpenVswitchDriver',
    'linuxnet_interface_driver': 'nova.network.linux_net.LinuxOVSInterfaceDriver',
    'quantum_use_dhcp': None,
}

#this is a special conf
CLEANER_DATA_CONF = 'nova-clean.sh'
CLEANER_CMD_ROOT = [sh.joinpths("/", "bin", 'bash')]

#pip files that nova requires
REQ_PIPS = ['general.json', 'nova.json']


class NovaUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)

    def pre_uninstall(self):
        self._clear_libvirt_domains()
        self._clean_it()

    def _clean_it(self):
        LOG.info("Cleaning up your system.")
        #these environment additions are important
        #in that they eventually affect how this script runs
        sub_components = self.component_opts or SUBCOMPONENTS
        env = dict()
        env['ENABLED_SERVICES'] = ",".join(sub_components)
        env['BIN_DIR'] = self.bindir
        env['VOLUME_NAME_PREFIX'] = self.cfg.get('nova', 'volume_name_prefix')
        cmd = CLEANER_CMD_ROOT + [sh.joinpths(self.bindir, CLEANER_DATA_CONF)]
        sh.execute(*cmd, run_as_root=True, env_overrides=env)

    def _clear_libvirt_domains(self):
        virt_driver = self.cfg.get('nova', 'virt_driver')
        if virt_driver == virsh.VIRT_TYPE:
            inst_prefix = self.cfg.get('nova', 'instance_name_prefix')
            libvirt_type = virsh.default(self.cfg.get('nova', 'libvirt_type'))
            virsh.clear_libvirt_domains(self.distro, libvirt_type, inst_prefix)


class NovaInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)
        self.paste_conf_fn = self._get_target_config_name(PASTE_CONF)
        self.volumes_enabled = False
        if not self.component_opts or NVOL in self.component_opts:
            self.volumes_enabled = True
        self.xvnc_enabled = False
        if not self.component_opts or NXVNC in self.component_opts:
            self.xvnc_enabled = True

    def _get_pkgs(self):
        pkgs = list(REQ_PKGS)
        sub_components = self.component_opts or SUBCOMPONENTS
        for c in sub_components:
            fns = ADD_PKGS.get(c)
            if fns:
                pkgs.extend(fns)
        return pkgs

    def _get_symlinks(self):
        links = dict()
        for fn in self._get_config_files():
            source_fn = self._get_target_config_name(fn)
            links[source_fn] = sh.joinpths("/", "etc", "nova", fn)
        source_fn = sh.joinpths(self.cfgdir, API_CONF)
        links[source_fn] = sh.joinpths("/", "etc", "nova", API_CONF)
        return links

    def _get_pips(self):
        return list(REQ_PIPS)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "nova_repo"),
            'branch': ("git", "nova_branch"),
        })
        return places

    def warm_configs(self):
        pws = ['rabbit']
        for pw_key in pws:
            self.cfg.get("passwords", pw_key)

    def _get_config_files(self):
        return list(CONFIGS)

    def _setup_network(self):
        LOG.info("Creating your nova network to be used with instances.")
        mp = dict()
        mp['BINDIR'] = self.bindir
        mp['CFGFILE'] = sh.joinpths(self.cfgdir, API_CONF)
        mp['FLOATING_RANGE'] = self.cfg.get('nova', 'floating_range')
        mp['TEST_FLOATING_RANGE'] = self.cfg.get('nova', 'test_floating_range')
        mp['TEST_FLOATING_POOL'] = self.cfg.get('nova', 'test_floating_pool')
        mp['FIXED_NETWORK_SIZE'] = self.cfg.get('nova', 'fixed_network_size')
        mp['FIXED_RANGE'] = self.cfg.get('nova', 'fixed_range')
        if settings.QUANTUM in self.instances:
            cmds = NETWORK_SETUP_CMDS[0:1]
        else:
            cmds = NETWORK_SETUP_CMDS
        utils.execute_template(*cmds, params=mp)

    def _sync_db(self):
        LOG.info("Syncing the database with nova.")
        mp = dict()
        mp['BINDIR'] = self.bindir
        mp['CFGFILE'] = sh.joinpths(self.cfgdir, API_CONF)
        utils.execute_template(*DB_SYNC_CMD, params=mp)

    def post_install(self):
        comp.PkgInstallComponent.post_install(self)
        #extra actions to do nova setup
        self._setup_db()
        self._sync_db()
        self._setup_network()
        self._setup_cleaner()
        # check if we need to do the vol subcomponent
        if self.volumes_enabled:
            vol_maker = NovaVolumeConfigurator(self)
            vol_maker.setup_volumes()

    def _setup_cleaner(self):
        LOG.info("Configuring cleaner template %s.", CLEANER_DATA_CONF)
        (_, contents) = utils.load_template(self.component_name, CLEANER_DATA_CONF)
        tgt_fn = sh.joinpths(self.bindir, CLEANER_DATA_CONF)
        sh.write_file(tgt_fn, contents)
        sh.chmod(tgt_fn, 755)
        self.tracewriter.file_touched(tgt_fn)

    def _setup_db(self):
        LOG.info("Fixing up database named %s.", DB_NAME)
        db.drop_db(self.cfg, DB_NAME)
        db.create_db(self.cfg, DB_NAME)

    def _generate_nova_conf(self):
        LOG.info("Generating dynamic content for nova configuration (%s)." % (API_CONF))
        component_dirs = dict()
        component_dirs['app'] = self.appdir
        component_dirs['cfg'] = self.cfgdir
        component_dirs['bin'] = self.bindir
        conf_gen = NovaConfConfigurator(self)
        nova_conf = conf_gen.configure(component_dirs)
        tgtfn = self._get_target_config_name(API_CONF)
        LOG.info("Writing nova configuration to %s" % (tgtfn))
        LOG.debug(nova_conf)
        self.tracewriter.make_dir(sh.dirname(tgtfn))
        sh.write_file(tgtfn, nova_conf)
        self.tracewriter.cfg_write(tgtfn)

    def _config_adjust(self, contents, config_fn):
        if config_fn == PASTE_CONF and settings.KEYSTONE in self.instances:
            newcontents = contents
            with io.BytesIO(contents) as stream:
                config = cfg.IgnoreMissingConfigParser()
                config.readfp(stream)
                mods = 0
                for section in PASTE_PIPELINE_KEYSTONE_ADJUST.keys():
                    if config.has_section(section):
                        section_vals = PASTE_PIPELINE_KEYSTONE_ADJUST.get(section)
                        for (k, v) in section_vals.items():
                            config.set(section, k, v)
                            mods += 1
                if mods > 0:
                    with io.BytesIO() as outputstream:
                        config.write(outputstream)
                        outputstream.flush()
                        newcontents = cfg.add_header(config_fn, outputstream.getvalue())
            contents = newcontents
        return contents

    def _get_source_config(self, config_fn):
        if config_fn == PASTE_CONF:
            #this is named differently than what it will be stored as... arg...
            srcfn = sh.joinpths(self.appdir, "etc", "nova", 'api-paste.ini')
            contents = sh.load_file(srcfn)
            return (srcfn, contents)
        else:
            return comp.PythonInstallComponent._get_source_config(self, config_fn)

    def _get_param_map(self, config_fn):
        return keystone.get_shared_params(self.cfg)

    def configure(self):
        am = comp.PythonInstallComponent.configure(self)
        #this is a special conf so we handle it ourselves
        self._generate_nova_conf()
        return am + 1


class NovaRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)

    def _get_apps_to_start(self):
        result = list()
        if not self.component_opts:
            apps = sorted(APP_OPTIONS.keys())
            for app_name in apps:
                result.append({
                    'name': app_name,
                    'path': sh.joinpths(self.bindir, app_name),
                })
        else:
            for short_name in self.component_opts:
                full_name = SUB_COMPONENT_NAME_MAP.get(short_name)
                if full_name and full_name in APP_OPTIONS:
                    result.append({
                        'name': full_name,
                        'path': sh.joinpths(self.bindir, full_name),
                    })
        return result

    def pre_start(self):
        virt_driver = self.cfg.get('nova', 'virt_driver')
        if virt_driver == virsh.VIRT_TYPE:
            virt_type = virsh.default(self.cfg.get('nova', 'libvirt_type'))
            LOG.info("Checking that your selected libvirt virtualization type [%s] is working and running." % (virt_type))
            if not virsh.virt_ok(virt_type, self.distro):
                msg = ("Libvirt type %s for distro %s does not seem to be active or configured correctly, "
                       "perhaps you should be using %s instead." % (virt_type, self.distro, virsh.DEFAULT_VIRT))
                raise exceptions.StartException(msg)
            virsh.restart(self.distro)

    def _get_param_map(self, app_name):
        params = comp.PythonRuntime._get_param_map(self, app_name)
        params['CFGFILE'] = sh.joinpths(self.cfgdir, API_CONF)
        return params

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)


#this will configure nova volumes which in a developer box
#is a volume group (lvm) that are backed by a loopback file
class NovaVolumeConfigurator(object):
    def __init__(self, ni):
        self.cfg = ni.cfg
        self.appdir = ni.appdir

    def setup_volumes(self):
        self._setup_vol_groups()

    def _setup_vol_groups(self):
        LOG.info("Attempting to setup volume groups for nova volume management.")
        mp = dict()
        backing_file = self.cfg.get('nova', 'volume_backing_file')
        # check if we need to have a default backing file
        if not backing_file:
            backing_file = sh.joinpths(self.appdir, 'nova-volumes-backing-file')
        vol_group = self.cfg.get('nova', 'volume_group')
        backing_file_size = utils.to_bytes(self.cfg.get('nova', 'volume_backing_file_size'))
        mp['VOLUME_GROUP'] = vol_group
        mp['VOLUME_BACKING_FILE'] = backing_file
        mp['VOLUME_BACKING_FILE_SIZE'] = backing_file_size
        try:
            utils.execute_template(*VG_CHECK_CMD, params=mp)
            LOG.warn("Volume group already exists: %s" % (vol_group))
        except exceptions.ProcessExecutionError as err:
            # Check that the error from VG_CHECK is an expected error
            if err.exit_code != 5:
                raise
            LOG.info("Need to create volume group: %s" % (vol_group))
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
        utils.execute_template(*RESTART_TGT_CMD, check_exit_code=False)

    def _process_lvs(self, mp):
        LOG.info("Attempting to setup logical volumes for nova volume management.")
        lvs_result = utils.execute_template(*VG_LVS_CMD, params=mp)
        if lvs_result and lvs_result[0]:
            LOG.debug("LVS result: %s" % (lvs_result))
            vol_name_prefix = self.cfg.get('nova', 'volume_name_prefix')
            LOG.debug("Using volume name prefix: %s" % (vol_name_prefix))
            (sysout, _) = lvs_result[0]
            for stdout_line in sysout.split('\n'):
                stdout_line = stdout_line.strip()
                if stdout_line:
                    # Ignore blank lines
                    LOG.debug("Processing LVS output line: %s" % (stdout_line))
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
class NovaConfConfigurator(object):
    def __init__(self, ni):
        self.cfg = ni.cfg
        self.instances = ni.instances
        self.component_root = ni.component_root
        self.appdir = ni.appdir
        self.tracewriter = ni.tracewriter
        self.paste_conf_fn = ni.paste_conf_fn
        self.distro = ni.distro
        self.xvnc_enabled = ni.xvnc_enabled
        self.volumes_enabled = ni.volumes_enabled

    def _getbool(self, name):
        return self.cfg.getboolean('nova', name)

    def _getstr(self, name):
        return self.cfg.get('nova', name)

    def configure(self, component_dirs):
        nova_conf = NovaConf()

        #use more than once
        hostip = self.cfg.get('host', 'ip')

        #verbose on?
        if self._getbool('verbose'):
            nova_conf.add_simple('verbose')

        #allow the admin api?
        if self._getbool('allow_admin_api'):
            nova_conf.add_simple('allow_admin_api')

        #which scheduler do u want?
        scheduler = self._getstr('scheduler')
        if not scheduler:
            scheduler = DEF_SCHEDULER
        nova_conf.add('scheduler_driver', scheduler)

        #setup network settings
        self._configure_network_settings(nova_conf, component_dirs)

        #setup nova volume settings
        if self.volumes_enabled:
            self._configure_vols(nova_conf)

        #where we are running
        nova_conf.add('my_ip', hostip)

        #setup your sql connection
        nova_conf.add('sql_connection', self.cfg.get_dbdsn('nova'))

        #configure anything libvirt releated?
        virt_driver = self._getstr('virt_driver')
        if virt_driver == virsh.VIRT_TYPE:
            libvirt_type = virsh.default(self._getstr('libvirt_type'))
            self._configure_libvirt(libvirt_type, nova_conf)

        #how instances will be presented
        instance_template = self._getstr('instance_name_prefix') + self._getstr('instance_name_postfix')
        nova_conf.add('instance_name_template', instance_template)

        #???
        nova_conf.add('osapi_compute_extension', 'nova.api.openstack.compute.contrib.standard_extensions')

        #vnc settings
        self._configure_vnc(nova_conf)

        #where our paste config is
        nova_conf.add('api_paste_config', self.paste_conf_fn)

        #what our imaging service will be
        self._configure_image_service(nova_conf)

        #ec2 / s3 stuff
        ec2_dmz_host = self._getstr('ec2_dmz_host')
        if not ec2_dmz_host:
            ec2_dmz_host = hostip
        nova_conf.add('ec2_dmz_host', ec2_dmz_host)
        nova_conf.add('s3_host', hostip)

        #how is your rabbit setup?
        nova_conf.add('rabbit_host', self.cfg.get('default', 'rabbit_host'))
        nova_conf.add('rabbit_password', self.cfg.get("passwords", "rabbit"))

        #where instances will be stored
        instances_path = self._getstr('instances_path')
        if not instances_path:
            instances_path = sh.joinpths(self.component_root, 'instances')
        self._configure_instances_path(instances_path, nova_conf)

        #is this a multihost setup?
        self._configure_multihost(nova_conf)

        #enable syslog??
        self._configure_syslog(nova_conf)

        #handle any virt driver specifics
        self._configure_virt_driver(nova_conf)

        #now make it
        conf_lines = sorted(nova_conf.generate())
        complete_file = utils.joinlinesep(*conf_lines)

        #add any extra flags in?
        extra_flags = self._getstr('extra_flags')
        if extra_flags:
            full_file = [complete_file, extra_flags]
            complete_file = utils.joinlinesep(*full_file)

        return complete_file

    def _configure_image_service(self, nova_conf):
        #what image service we will use
        img_service = self._getstr('img_service')
        if not img_service:
            img_service = DEF_IMAGE_SERVICE
        nova_conf.add('image_service', img_service)

        #where is glance located?
        if img_service.lower().find("glance") != -1:
            glance_api_server = self._getstr('glance_server')
            if not glance_api_server:
                glance_api_server = "%s:%d" % (self.cfg.get('host', 'ip'),
                                               DEF_GLANCE_PORT)
            nova_conf.add('glance_api_servers', glance_api_server)

    def _configure_vnc(self, nova_conf):
        if settings.NOVNC in self.instances:
            vncproxy_url = self._getstr('vncproxy_url')
            nova_conf.add('novncproxy_base_url', vncproxy_url)

        if self.xvnc_enabled:
            nova_conf.add('xvpvncproxy_base_url', self._getstr('xvpvncproxy_url'))
        nova_conf.add('vncserver_listen', self._getstr('vncserver_listen'))
        vncserver_proxyclient_address = self._getstr('vncserver_proxyclient_address')

        # If no vnc proxy address was specified, pick a default based on which
        # driver we're using
        virt_driver = self._getstr('virt_driver')
        if not vncserver_proxyclient_address:
            if virt_driver == 'xenserver':
                vncserver_proxyclient_address = '169.254.0.1'
            else:
                vncserver_proxyclient_address = '127.0.0.1'

        nova_conf.add('vncserver_proxyclient_address', vncserver_proxyclient_address)

    def _configure_vols(self, nova_conf):
        nova_conf.add('volume_group', self._getstr('volume_group'))
        volume_name_template = self._getstr('volume_name_prefix') + self._getstr('volume_name_postfix')
        nova_conf.add('volume_name_template', volume_name_template)
        nova_conf.add('iscsi_help', 'tgtadm')

    def _configure_network_settings(self, nova_conf, component_dirs):
        if settings.QUANTUM in self.instances:
            nova_conf.add('network_manager', QUANTUM_MANAGER)
            nova_conf.add('quantum_connection_host', self.cfg.get('quantum', 'q_host'))
            nova_conf.add('quantum_connection_port', self.cfg.get('quantum', 'q_port'))
            if self.cfg.get('quantum', 'q_plugin') == 'openvswitch':
                for (key, value) in QUANTUM_OPENSWITCH_OPS.items():
                    if value is None:
                        nova_conf.add_simple(key)
                    else:
                        nova_conf.add(key, value)
            if settings.MELANGE_CLIENT in self.instances:
                nova_conf.add('quantum_ipam_lib', 'nova.network.quantum.melange_ipam_lib')
                nova_conf.add_simple('use_melange_mac_generation')
                nova_conf.add('melange_host', self.cfg.get('melange', 'm_host'))
                nova_conf.add('melange_port', self.cfg.get('melange', 'm_port'))
        else:
            nova_conf.add('network_manager', NET_MANAGER_TEMPLATE % (self._getstr('network_manager')))

        #dhcp bridge stuff???
        flag_conf_fn = sh.joinpths(component_dirs.get('cfg'), API_CONF)
        nova_conf.add('dhcpbridge_flagfile', flag_conf_fn)

        #Network prefix for the IP network that all the projects for future VM guests reside on. Example: 192.168.0.0/12
        nova_conf.add('fixed_range', self._getstr('fixed_range'))

        # The value for vlan_interface may default to the the current value
        # of public_interface. We'll grab the value and keep it handy.
        public_interface = self._getstr('public_interface')
        vlan_interface = self._getstr('vlan_interface')
        if not vlan_interface:
            vlan_interface = public_interface

        #do a little check to make sure actually have that interface set...
        known_interfaces = utils.get_interfaces()
        if not public_interface in known_interfaces:
            msg = "Public interface %s is not a known interface" % (public_interface)
            raise exceptions.ConfigException(msg)
        if not vlan_interface in known_interfaces:
            msg = "VLAN interface %s is not a known interface" % (vlan_interface)
            raise exceptions.ConfigException(msg)
        nova_conf.add('public_interface', public_interface)
        nova_conf.add('vlan_interface', vlan_interface)

        #This forces dnsmasq to update its leases table when an instance is terminated.
        nova_conf.add_simple('force_dhcp_release')

    def _configure_syslog(self, nova_conf):
        if self.cfg.getboolean('default', 'syslog'):
            nova_conf.add_simple('use_syslog')

    def _configure_multihost(self, nova_conf):
        if self._getbool('multi_host'):
            nova_conf.add_simple('multi_host')
            nova_conf.add_simple('send_arp_for_ha')

    def _configure_instances_path(self, instances_path, nova_conf):
        nova_conf.add('instances_path', instances_path)
        LOG.debug("Attempting to create instance directory: %s" % (instances_path))
        self.tracewriter.make_dir(instances_path)
        LOG.debug("Adjusting permissions of instance directory: %s" % (instances_path))
        os.chmod(instances_path, stat.S_IRWXO | stat.S_IRWXG | stat.S_IRWXU)

    def _configure_libvirt(self, virt_type, nova_conf):
        if virt_type == 'lxc':
            #TODO need to add some goodies here
            pass
        nova_conf.add('libvirt_type', virt_type)

    #configures any virt driver settings
    def _configure_virt_driver(self, nova_conf):
        driver = self._getstr('virt_driver')
        drive_canon = driver.lower().strip()
        if drive_canon == 'xenserver':
            nova_conf.add('connection_type', 'xenapi')
            nova_conf.add('xenapi_connection_url', 'http://169.254.0.1')
            nova_conf.add('xenapi_connection_username', 'root')
            nova_conf.add('xenapi_connection_password', self.cfg.get("passwords", "xenapi_connection"))
            nova_conf.add_simple('noflat_injected')
            nova_conf.add('flat_interface', 'eth1')
            nova_conf.add('firewall_driver', self._getstr('xen_firewall_driver'))
            nova_conf.add('flat_network_bridge', 'xapi1')
        else:
            nova_conf.add('connection_type', 'libvirt')
            nova_conf.add('firewall_driver', self._getstr('libvirt_firewall_driver'))
            nova_conf.add('flat_network_bridge', self._getstr('flat_network_bridge'))
            flat_interface = self._getstr('flat_interface')
            if flat_interface:
                nova_conf.add('flat_interface', flat_interface)


# This class represents the data in the nova config file
class NovaConf(object):
    def __init__(self):
        self.lines = list()

    def add_list(self, key, *params):
        self.lines.append({'key': key, 'options': params})
        LOG.debug("Added nova conf key %s with values [%s]" % (key, ",".join(params)))

    def add_simple(self, key):
        self.lines.append({'key': key, 'options': None})
        LOG.debug("Added nova conf key %s" % (key))

    def add(self, key, value):
        self.lines.append({'key': key, 'options': [value]})
        LOG.debug("Added nova conf key %s with value [%s]" % (key, value))

    def _form_key(self, key, has_opts):
        key_str = "--" + str(key)
        if has_opts:
            key_str += "="
        return key_str

    def generate(self, param_dict=None):
        gen_lines = list()
        for line_entry in self.lines:
            key = line_entry.get('key')
            opts = line_entry.get('options')
            if not key:
                continue
            if opts is None:
                key_str = self._form_key(key, False)
                full_line = key_str
            else:
                key_str = self._form_key(key, True)
                filled_opts = list()
                for opt in opts:
                    filled_opts.append(utils.param_replace(str(opt), param_dict))
                full_line = key_str + ",".join(filled_opts)
            gen_lines.append(full_line)
        return gen_lines
