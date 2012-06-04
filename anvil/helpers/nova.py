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


import os
import weakref

from anvil import cfg
from anvil import exceptions
from anvil import libvirt as lv
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.helpers import db as dbhelper

LOG = logging.getLogger(__name__)

# Paste configuration
PASTE_CONF = 'nova-api-paste.ini'

# Special generated conf
API_CONF = 'nova.conf'

# This db will be dropped then created
DB_NAME = 'nova'

# Network class/driver/manager templs

# These are only used if quantum is active
QUANTUM_MANAGER = 'nova.network.quantum.manager.QuantumManager'
QUANTUM_IPAM_LIB = 'nova.network.quantum.melange_ipam_lib'

# Sensible defaults
DEF_IMAGE_SERVICE = 'nova.image.glance.GlanceImageService'
DEF_SCHEDULER = 'nova.scheduler.filter_scheduler.FilterScheduler'
DEF_GLANCE_PORT = 9292
DEF_GLANCE_SERVER = "%s" + ":%s" % (DEF_GLANCE_PORT)
DEF_INSTANCE_PREFIX = 'instance-'
DEF_INSTANCE_TEMPL = DEF_INSTANCE_PREFIX + '%08x'
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

# Known mq types
MQ_TYPES = ['rabbit', 'qpid', 'zeromq']

# Xenserver specific defaults
XS_DEF_INTERFACE = 'eth1'
XA_CONNECTION_ADDR = '169.254.0.1'
XS_VNC_ADDR = XA_CONNECTION_ADDR
XS_DEF_BRIDGE = 'xapi1'
XA_CONNECTION_PORT = 80
XA_DEF_USER = 'root'
XA_DEF_CONNECTION_URL = utils.make_url('http', XA_CONNECTION_ADDR, XA_CONNECTION_PORT)

# Vnc specific defaults
VNC_DEF_ADDR = '127.0.0.1'

# Nova std compute extensions
STD_COMPUTE_EXTS = 'nova.api.openstack.compute.contrib.standard_extensions'


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


def canon_mq_type(mq_type):
    if not mq_type:
        return ''
    return str(mq_type).lower().strip()


def canon_virt_driver(virt_driver):
    if not virt_driver:
        return DEF_VIRT_DRIVER
    virt_driver = virt_driver.strip().lower()
    if not (virt_driver in VIRT_DRIVER_CON_MAP):
        return DEF_VIRT_DRIVER
    return virt_driver


def get_shared_params(cfgobj):
    mp = dict()

    host_ip = cfgobj.get('host', 'ip')
    mp['service_host'] = host_ip
    nova_host = cfgobj.getdefaulted('nova', 'nova_host', host_ip)
    nova_protocol = cfgobj.getdefaulted('nova', 'nova_protocol', 'http')

    # Uri's of the various nova endpoints
    mp['endpoints'] = {
        'ec2_admin': {
            'uri': utils.make_url(nova_protocol, nova_host, 8773, "services/Admin"),
            'port': 8773,
            'host': host_ip,
            'protocol': nova_protocol,
        },
        'ec2_cloud': {
            'uri': utils.make_url(nova_protocol, nova_host, 8773, "services/Cloud"),
            'port': 8773,
            'host': host_ip,
            'protocol': nova_protocol,
        },
        'volume': {
            'uri': utils.make_url(nova_protocol, host_ip, 8776, "v1"),
            'port': 8776,
            'host': host_ip,
            'protocol': nova_protocol,
        },
        's3': {
            'uri': utils.make_url('http', host_ip, 3333),
            'port': 3333,
            'host': host_ip,
            'protocol': nova_protocol,
        },
        'api': {
            'uri': utils.make_url('http', host_ip, 8774, "v2"),
            'port': 8774,
            'host': host_ip,
            'protocol': nova_protocol,
        },
    }

    return mp


# This will configure nova volumes which in a developer box
# is a volume group (lvm) that are backed by a loopback file
class VolumeConfigurator(object):
    def __init__(self, installer):
        self.installer = weakref.proxy(installer)
        self.distro = installer.distro
        self.cfg = self.installer.cfg

    def setup_volumes(self):
        self._setup_vol_groups()

    def verify(self):
        pass

    def _setup_vol_groups(self):
        LOG.info("Attempting to setup volume groups for nova volume management.")
        mp = dict()
        backing_file = self.cfg.getdefaulted('nova', 'volume_backing_file',
                       sh.joinpths(self.installer.get_option('app_dir'), 'nova-volumes-backing-file'))
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
class ConfConfigurator(object):

    def __init__(self, installer):
        self.installer = weakref.proxy(installer)
        self.cfg = installer.cfg
        self.instances = installer.instances
        self.tracewriter = installer.tracewriter
        self.paste_conf_fn = installer._get_target_config_name(PASTE_CONF)
        self.distro = installer.distro
        self.xvnc_enabled = installer.xvnc_enabled
        self.volumes_enabled = installer.volumes_enabled

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
        mq_type = canon_mq_type(self.installer.get_option('mq'))
        if mq_type not in MQ_TYPES:
            msg = "Unknown message queue type %s (is it one of %s??)" % (mq_type, ", ".join(MQ_TYPES))
            raise exceptions.ConfigException(msg)

    def configure(self, fn=API_CONF, root_wrapped=False):

        # Everything built goes in here
        nova_conf = Conf(fn)

        # Used more than once so we calculate it ahead of time
        hostip = self.cfg.get('host', 'ip')

        if self._getbool('verbose'):
            nova_conf.add('verbose', True)

        # Allow the admin api?
        if self._getbool('allow_admin_api'):
            nova_conf.add('allow_admin_api', True)

        # FIXME: ??
        nova_conf.add('allow_resize_to_same_host', True)

        # Which scheduler do u want?
        nova_conf.add('compute_scheduler_driver', self._getstr('scheduler', DEF_SCHEDULER))

        # Rate limit the api??
        nova_conf.add('api_rate_limit', self._getbool('api_rate_limit'))

        # Setup any network settings
        self._configure_network_settings(nova_conf)

        # Setup nova volume settings
        if self.volumes_enabled:
            self._configure_vols(nova_conf)

        # The ip of where we are running
        nova_conf.add('my_ip', hostip)

        # Setup your sql connection
        nova_conf.add('sql_connection', dbhelper.fetch_dbdsn(self.cfg, DB_NAME))

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

        # Don't always force images to raw
        nova_conf.add('force_raw_images', self._getbool('force_raw_images'))

        # Vnc settings setup
        self._configure_vnc(nova_conf)

        # Where our paste config is
        nova_conf.add('api_paste_config', self.paste_conf_fn)

        # What our imaging service will be
        self._configure_image_service(nova_conf, hostip)

        # Configs for ec2 / s3 stuff
        nova_conf.add('ec2_dmz_host', self._getstr('ec2_dmz_host', hostip))
        nova_conf.add('s3_host', hostip)

        # How is your mq setup?
        mq_type = canon_mq_type(self.installer.get_option('mq'))
        if mq_type == 'rabbit':
            nova_conf.add('rabbit_host', self.cfg.getdefaulted('rabbit', 'rabbit_host', hostip))
            nova_conf.add('rabbit_password', self.cfg.get("passwords", "rabbit"))
            nova_conf.add('rpc_backend', 'nova.rpc.impl_kombu')
        elif mq_type == 'qpid':
            nova_conf.add('rpc_backend', 'nova.rpc.impl_qpid')
        elif mq_type == 'zeromq':
            # TODO more needed???
            nova_conf.add('rpc_backend', 'nova.rpc.impl_kombu')

        # Where instances will be stored
        instances_path = self._getstr('instances_path', sh.joinpths(self.installer.get_option('component_dir'), 'instances'))
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
        if self.installer.get_option('no-vnc'):
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

    # Fixes up your nova volumes
    def _configure_vols(self, nova_conf):
        nova_conf.add('volume_group', self._getstr('volume_group'))
        vol_name_tpl = self._getstr('volume_name_prefix') + self._getstr('volume_name_postfix')
        if not vol_name_tpl:
            vol_name_tpl = DEF_VOL_TEMPL
        nova_conf.add('volume_name_template', vol_name_tpl)
        nova_conf.add('iscsi_helper', 'tgtadm')

    def _configure_network_settings(self, nova_conf):
        # TODO this might not be right....
        if self.installer.get_option('quantum'):
            nova_conf.add('network_manager', QUANTUM_MANAGER)
            hostip = self.cfg.get('host', 'ip')
            nova_conf.add('quantum_connection_host', self.cfg.getdefaulted('quantum', 'q_host', hostip))
            nova_conf.add('quantum_connection_port', self.cfg.getdefaulted('quantum', 'q_port', '9696'))
            if self.cfg.get('quantum', 'q_plugin') == 'openvswitch':
                for (key, value) in QUANTUM_OPENSWITCH_OPS.items():
                    nova_conf.add(key, value)
            if self.installer.get_option('melange'):
                nova_conf.add('quantum_ipam_lib', QUANTUM_IPAM_LIB)
                nova_conf.add('use_melange_mac_generation', True)
                nova_conf.add('melange_host', self.cfg.getdefaulted('melange', 'm_host', hostip))
                nova_conf.add('melange_port', self.cfg.getdefaulted('melange', 'm_port', '9898'))
        else:
            nova_conf.add('network_manager', self._getstr('network_manager'))

        # Configs dhcp bridge stuff???
        # TODO: why is this the same as the nova.conf?
        nova_conf.add('dhcpbridge_flagfile', sh.joinpths(self.installer.get_option('cfg_dir'), API_CONF))

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

        # Special virt driver network settings
        drive_canon = canon_virt_driver(self._getstr('virt_driver'))
        if drive_canon == 'xenserver':
            nova_conf.add('noflat_injected', True)
            nova_conf.add('flat_network_bridge', self._getstr('xs_flat_network_bridge', XS_DEF_BRIDGE))
            xs_flat_ifc = self._getstr('xs_flat_interface', XS_DEF_INTERFACE)
            if xs_flat_ifc:
                nova_conf.add('flat_interface', xs_flat_ifc)
        else:
            nova_conf.add('flat_network_bridge', self._getstr('flat_network_bridge', DEF_FLAT_VIRT_BRIDGE))
            nova_conf.add('flat_injected', self._getbool('flat_injected'))
            flat_interface = self._getstr('flat_interface')
            if flat_interface:
                nova_conf.add('flat_interface', flat_interface)

    # Enables multihost (??)
    def _configure_multihost(self, nova_conf):
        if self._getbool('multi_host'):
            nova_conf.add('multi_host', True)
            nova_conf.add('send_arp_for_ha', True)

    # Ensures the place where instances will be is useable
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

    # Any special libvirt configurations go here
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
            nova_conf.add('firewall_driver', self._getstr('xs_firewall_driver'))
        elif drive_canon == 'libvirt':
            nova_conf.add('firewall_driver', self._getstr('libvirt_firewall_driver'))
        else:
            nova_conf.add('firewall_driver', self._getstr('basic_firewall_driver'))


# This class represents the data/format of the nova config file
class Conf(object):
    def __init__(self, name):
        self.backing = cfg.BuiltinConfigParser()
        self.name = name

    def add(self, key, value, *values):
        real_key = str(key)
        real_value = ""
        if len(values):
            str_values = [str(value)] + [str(v) for v in values]
            real_value = ",".join(str_values)
        else:
            real_value = str(value)
        self.backing.set('DEFAULT', real_key, real_value)
        LOG.debug("Added nova conf key %r with value %r" % (real_key, real_value))

    def generate(self):
        return self.backing.stringify(fn=self.name)
