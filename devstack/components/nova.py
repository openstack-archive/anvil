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
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

from devstack.components import db
from devstack.components import keystone

LOG = logging.getLogger('devstack.components.nova')

#special generatedconf
API_CONF = 'nova.conf'

#normal conf
PASTE_CONF = 'nova-api-paste.ini'
CONFIGS = [PASTE_CONF]

#this db will be dropped then created
DB_NAME = 'nova'

#id
TYPE = settings.NOVA

DB_SYNC_CMD = [
    {'cmd': ['%BINDIR%/nova-manage', '--flagfile', '%CFGFILE%',
             'db', 'sync']},
]

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
SUBCOMPONENTS = [NCPU, NVOL, NAPI,
    NOBJ, NNET, NCERT, NSCHED, NCAUTH]


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
    'ec2cloud': 'ec2faultwrap logrequest totoken authtoken keystonecontext cloudrequest authorizer validator ec2executor',
    'ec2admin': "ec2faultwrap logrequest totoken authtoken keystonecontext adminrequest authorizer ec2executor",
    'openstack_compute_api_v2': "faultwrap authtoken keystonecontext ratelimit osapi_compute_app_v2",
    'openstack_volume_api_v1': "faultwrap authtoken keystonecontext ratelimit osapi_volume_app_v1",
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
}

#subdirs of the checkout/download
BIN_DIR = 'bin'

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

#pip files that nova requires
REQ_PIPS = ['nova.json']


class NovaUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)


class NovaInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)
        self.paste_conf_fn = self._get_target_config_name(PASTE_CONF)

    def _get_pkgs(self):
        pkgs = list(REQ_PKGS)
        sub_components = self.component_opts or SUBCOMPONENTS
        for c in sub_components:
            fns = ADD_PKGS.get(c) or []
            pkgs.extend(fns)
        return pkgs

    def _get_pips(self):
        return list(REQ_PIPS)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "nova_repo"),
            'branch': ("git", "nova_branch"),
        })
        return places

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
        utils.execute_template(*cmds, params=mp, tracewriter=self.tracewriter)

    def _sync_db(self):
        LOG.info("Syncing the database with nova.")
        mp = dict()
        mp['BINDIR'] = self.bindir
        mp['CFGFILE'] = sh.joinpths(self.cfgdir, API_CONF)
        utils.execute_template(*DB_SYNC_CMD, params=mp, tracewriter=self.tracewriter)

    def post_install(self):
        parent_result = comp.PkgInstallComponent.post_install(self)
        #extra actions to do nova setup
        self._setup_db()
        self._sync_db()
        self._setup_network()
        # check if we need to do the vol subcomponent
        if not self.component_opts or NVOL in self.component_opts:
            # yes, either no subcomponents were specifically requested or it's
            # in the set that was requested
            self._setup_vol_groups()
        return parent_result

    def _setup_db(self):
        LOG.info("Fixing up database named %s.", DB_NAME)
        db.drop_db(self.cfg, DB_NAME)
        db.create_db(self.cfg, DB_NAME)

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
            LOG.debug("vg dev result:%s" % (vg_dev_result))
            # Strip the newlines out of the stdout (which is in the first
            # element of the first (and only) tuple in the response
            mp['DEV'] = vg_dev_result[0][0].replace('\n', '')
            utils.execute_template(*VG_CREATE_CMD, params=mp, tracewriter=self.tracewriter)
        # One way or another, we should have the volume group, Now check the
        # logical volumes
        self._process_lvs(mp)
        # Finish off by restarting tgt, and ignore any errors
        utils.execute_template(*RESTART_TGT_CMD, check_exit_code=False, tracewriter=self.tracewriter)

    def _process_lvs(self, mp):
        LOG.info("Attempting to setup logical volumes for nova volume management.")
        lvs_result = utils.execute_template(*VG_LVS_CMD, params=mp, tracewriter=self.tracewriter)
        LOG.debug("lvs result: %s" % (lvs_result))
        vol_name_prefix = self.cfg.get('nova', 'volume_name_prefix')
        LOG.debug("Using volume name prefix: %s" % (vol_name_prefix))
        for stdout_line in lvs_result[0][0].split('\n'):
            if stdout_line:
                # Ignore blank lines
                LOG.debug("lvs output line:%s" % (stdout_line))
                if stdout_line.startswith(vol_name_prefix):
                    # TODO still need to implement the following:
                    # tid=`egrep "^tid.+$lv" /proc/net/iet/volume | cut -f1 -d' ' | tr ':' '='`
                    # if [[ -n "$tid" ]]; then
                    #   lun=`egrep "lun.+$lv" /proc/net/iet/volume | cut -f1 -d' ' | tr ':' '=' | tr -d '\t'`
                    #   sudo ietadm --op delete --$tid --$lun
                    # fi
                    # sudo lvremove -f $VOLUME_GROUP/$lv
                    raise exceptions.StackException("lvs magic not yet implemented")
                mp['LV'] = stdout_line
                utils.execute_template(*VG_LVREMOVE_CMD, params=mp, tracewriter=self.tracewriter)

    def _generate_nova_conf(self):
        LOG.info("Generating dynamic content for nova configuration (%s)." % (API_CONF))
        dirs = dict()
        dirs['app'] = self.appdir
        dirs['cfg'] = self.cfgdir
        dirs['bin'] = self.bindir
        conf_gen = NovaConfigurator(self)
        nova_conf = conf_gen.configure(dirs)
        tgtfn = self._get_target_config_name(API_CONF)
        LOG.info("Writing conf to %s" % (tgtfn))
        LOG.info(nova_conf)
        sh.write_file(tgtfn, nova_conf)
        self.tracewriter.cfg_write(tgtfn)

    def _config_adjust(self, contents, config_fn):
        if config_fn == PASTE_CONF and settings.KEYSTONE in self.instances:
            #We change the pipelines in nova to use keystone
            newcontents = contents
            with io.BytesIO(contents) as stream:
                config = cfg.IgnoreMissingConfigParser()
                config.readfp(stream)
                adjusted_pipelines = 0
                for (name, value) in PASTE_PIPELINE_KEYSTONE_ADJUST.items():
                    section_name = "pipeline:" + name
                    if config.has_section(section_name):
                        LOG.debug("Adjusting section named \"%s\" option \"pipeline\" to \"%s\"", section_name, value)
                        config.set(section_name, "pipeline", value)
                        adjusted_pipelines += 1
                if adjusted_pipelines:
                    #we changed it, guess we have to write it out
                    with io.BytesIO() as outputstream:
                        config.write(outputstream)
                        outputstream.flush()
                        #TODO can we write to contents here directly?
                        newcontents = outputstream.getvalue()
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

    def _get_target_config_name(self, config_fn):
        if config_fn == PASTE_CONF:
            #TODO Don't put nova-api-paste.ini in bin?
            return sh.joinpths(self.appdir, "bin", 'nova-api-paste.ini')
        else:
            return comp.PythonInstallComponent._get_target_config_name(self, config_fn)

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

    def _get_apps_to_start(self):
        result = list()
        if not self.component_opts:
            apps = sorted(APP_OPTIONS.keys())
            for app_name in apps:
                result.append({
                    'name': app_name,
                    'path': sh.joinpths(self.appdir, BIN_DIR, app_name),
                })
        else:
            for short_name in self.component_opts:
                full_name = SUB_COMPONENT_NAME_MAP.get(short_name)
                if full_name and full_name in APP_OPTIONS:
                    result.append({
                        'name': full_name,
                        'path': sh.joinpths(self.appdir, BIN_DIR, full_name),
                    })
        return result

    def _get_param_map(self, app_name):
        params = comp.PythonRuntime._get_param_map(self, app_name)
        params['CFGFILE'] = sh.joinpths(self.cfgdir, API_CONF)
        return params

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)


# This class has the smarts to build the configuration file based on
# various runtime values
class NovaConfigurator(object):
    def __init__(self, nc):
        self.cfg = nc.cfg
        self.instances = nc.instances
        self.component_root = nc.component_root
        self.appdir = nc.appdir
        self.tracewriter = nc.tracewriter
        self.paste_conf_fn = nc.paste_conf_fn
        self.nvol = not nc.component_opts or NVOL in nc.component_opts

    def _getbool(self, name):
        return self.cfg.getboolean('nova', name)

    def _getstr(self, name):
        return self.cfg.get('nova', name)

    def configure(self, dirs):

        #TODO split up into sections??

        nova_conf = NovaConf()
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

        flag_conf_fn = sh.joinpths(dirs.get('cfg'), API_CONF)
        nova_conf.add('dhcpbridge_flagfile', flag_conf_fn)

        #whats the network fixed range?
        nova_conf.add('fixed_range', self._getstr('fixed_range'))

        if settings.QUANTUM in self.instances:
            #setup quantum config
            nova_conf.add('network_manager', QUANTUM_MANAGER)
            nova_conf.add('quantum_connection_host', self.cfg.get('quantum', 'q_host'))
            nova_conf.add('quantum_connection_port', self.cfg.get('quantum', 'q_port'))
            if self.cfg.get('quantum', 'q_plugin') == 'openvswitch':
                for (key, value) in QUANTUM_OPENSWITCH_OPS.items():
                    if value is None:
                        nova_conf.add_simple(key)
                    else:
                        nova_conf.add(key, value)
        else:
            nova_conf.add('network_manager', NET_MANAGER_TEMPLATE % (self._getstr('network_manager')))

        if self.nvol:
            nova_conf.add('volume_group', self._getstr('volume_group'))
            volume_name_template = self._getstr('volume_name_prefix') + self._getstr('volume_name_postfix')
            nova_conf.add('volume_name_template', volume_name_template)
            nova_conf.add('iscsi_help', 'tgtadm')
        nova_conf.add('my_ip', hostip)

        # The value for vlan_interface may default to the the current value
        # of public_interface. We'll grab the value and keep it handy.
        public_interface = self._getstr('public_interface')
        vlan_interface = self._getstr('vlan_interface')
        if not vlan_interface:
            vlan_interface = public_interface
        nova_conf.add('public_interface', public_interface)
        nova_conf.add('vlan_interface', vlan_interface)

        #setup your sql connection and what type of virt u will be doing
        nova_conf.add('sql_connection', self.cfg.get_dbdsn('nova'))

        #configure anything libvirt releated?
        self._configure_libvirt(self._getstr('libvirt_type'), nova_conf)

        #how instances will be presented
        instance_template = self._getstr('instance_name_prefix') + self._getstr('instance_name_postfix')
        nova_conf.add('instance_name_template', instance_template)

        nova_conf.add('osapi_compute_extension', 'nova.api.openstack.compute.contrib.standard_extensions')

        if settings.NOVNC in self.instances:
            vncproxy_url = self._getstr('vncproxy_url')
            nova_conf.add('novncproxy_base_url', vncproxy_url)

        if settings.XVNC in self.instances:
            xvncproxy_url = self._getstr('xvpvncproxy_url')
            nova_conf.add('xvpvncproxy_base_url', xvncproxy_url)

        nova_conf.add('vncserver_listen', self._getstr('vncserver_listen'))
        vncserver_proxyclient_address = self._getstr('vncserver_proxyclient_addres')
        # If no vnc proxy address was specified, pick a default based on which
        # driver we're using
        virt_driver = self._getstr('virt_driver')
        if not vncserver_proxyclient_address:
            if virt_driver == 'xenserver':
                vncserver_proxyclient_address = '169.254.0.1'
            else:
                vncserver_proxyclient_address = '127.0.0.1'

        nova_conf.add('vncserver_proxyclient_address', vncserver_proxyclient_address)
        nova_conf.add('api_paste_config', self.paste_conf_fn)

        img_service = self._getstr('img_service')
        if not img_service:
            img_service = DEF_IMAGE_SERVICE
        nova_conf.add('image_service', img_service)

        ec2_dmz_host = self._getstr('ec2_dmz_host')
        if not ec2_dmz_host:
            ec2_dmz_host = hostip
        nova_conf.add('ec2_dmz_host', ec2_dmz_host)

        #how is your rabbit setup?
        nova_conf.add('rabbit_host', self.cfg.get('default', 'rabbit_host'))
        nova_conf.add('rabbit_password', self.cfg.get("passwords", "rabbit"))

        #where is glance located?
        glance_api_server = self._getstr('glance_server')
        if not glance_api_server:
            glance_api_server = "%s:%d" % (hostip, DEF_GLANCE_PORT)
        nova_conf.add('glance_api_servers', glance_api_server)
        nova_conf.add_simple('force_dhcp_release')

        #where instances will be stored
        instances_path = self._getstr('instances_path')
        if not instances_path:
            # If there's no instances path, specify a default
            instances_path = sh.joinpths(self.component_root, 'instances')
        nova_conf.add('instances_path', instances_path)

        # Create the directory for instances
        LOG.debug("Attempting to create instance directory: %s" % (instances_path))
        self.tracewriter.make_dir(instances_path)
        LOG.debug("Adjusting permissions of instance directory: %s" % (instances_path))
        os.chmod(instances_path, stat.S_IRWXO | stat.S_IRWXG | stat.S_IRWXU)

        #is this a multihost setup?
        if self._getbool('multi_host'):
            nova_conf.add_simple('multi_host')
            nova_conf.add_simple('send_arp_for_ha')

        #enable syslog??
        if self.cfg.getboolean('default', 'syslog'):
            nova_conf.add_simple('use_syslog')

        #handle any virt driver specifics
        self._configure_virt_driver(virt_driver, nova_conf)

        #now make it
        conf_lines = sorted(nova_conf.generate())
        complete_file = utils.joinlinesep(*conf_lines)

        #add any extra flags in?
        extra_flags = self._getstr('extra_flags')
        if extra_flags and len(extra_flags):
            full_file = [complete_file, extra_flags]
            complete_file = utils.joinlinesep(*full_file)

        return complete_file

    def _configure_libvirt(self, virt_type, nova_conf):
        if not virt_type:
            return
        nova_conf.add('libvirt_type', virt_type)

    #configures any virt driver settings
    def _configure_virt_driver(self, driver, nova_conf):
        if not driver:
            return
        drive_canon = driver.lower().strip()
        if drive_canon == 'xenserver':
            nova_conf.add('connection_type', 'xenapi')
            nova_conf.add('xenapi_connection_url', 'http://169.254.0.1')
            nova_conf.add('xenapi_connection_username', 'root')
            nova_conf.add('xenapi_connection_password', self.cfg.get("passwords", "xenapi_connection"))
            nova_conf.add_simple('noflat_injected')
            nova_conf.add('flat_interface', 'eth1')
            nova_conf.add('firewall_driver', self.cfg.getstr('xen_firewall_driver'))
            nova_conf.add('flat_network_bridge', 'xapi1')
        else:
            nova_conf.add('connection_type', 'libvirt')
            nova_conf.add('firewall_driver', self.cfg.getstr('libvirt_firewall_driver'))
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


def describe(opts=None):
    description = """
 Module: {module_name}
  Description:
   {description}
  Component options:
   {component_opts}
"""
    params = dict()
    params['component_opts'] = "TBD"
    params['module_name'] = __name__
    params['description'] = __doc__ or "Handles actions for the nova component."
    out = description.format(**params)
    return out.strip("\n")
