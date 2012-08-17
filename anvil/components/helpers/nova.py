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

from anvil.components.helpers import db as dbhelper

LOG = logging.getLogger(__name__)

# Paste configuration
PASTE_CONF = 'nova-api-paste.ini'

# Special generated conf
API_CONF = 'nova.conf'

# This db will be dropped then created
DB_NAME = 'nova'

# Network class/driver/manager templs

# Default virt types
DEF_VIRT_DRIVER = 'libvirt'

# Virt drivers map -> to there connection name
VIRT_DRIVER_CON_MAP = {
    'libvirt': 'libvirt',
}


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
        self.distro = installer.distro

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
        if drive_canon == 'libvirt':
            flat_interface = self._getstr('flat_interface')
            if flat_interface and not flat_interface in known_interfaces:
                msg = "Libvirt flat interface %s is not a known interface (is it one of %s??)" % (flat_interface, ", ".join(known_interfaces))
                raise exceptions.ConfigException(msg)
        mq_type = canon_mq_type(self.installer.get_option('mq'))
        if mq_type not in ['rabbit']:
            msg = "Unknown message queue type %s (is it one of %s??)" % (mq_type, ", ".join(['rabbit']))
            raise exceptions.ConfigException(msg)

    def generate(self, fn):

        # Everything built goes in here
        nova_conf = Conf(fn)

        # Used more than once so we calculate it ahead of time
        hostip = self.cfg.get('host', 'ip')

        if self._getbool('verbose'):
            nova_conf.add('verbose', True)

        # Allow destination machine to match source for resize. 
        nova_conf.add('allow_resize_to_same_host', True)

        # Which scheduler do u want?
        nova_conf.add('compute_scheduler_driver', self._getstr('scheduler', 'nova.scheduler.filter_scheduler.FilterScheduler'))

        # Rate limit the api??
        nova_conf.add('api_rate_limit', self._getbool('api_rate_limit'))

        # Setup nova network/settings
        self._configure_network_settings(nova_conf)

        # Setup nova volume/settings
        if self.installer.get_option('volumes'):
            self._configure_vols(nova_conf)

        # The ip of where we are running
        nova_conf.add('my_ip', hostip)

        # Setup your sql connection
        nova_conf.add('sql_connection', dbhelper.fetch_dbdsn(self.cfg, DB_NAME))

        # Configure anything libvirt related?
        virt_driver = canon_virt_driver(self._getstr('virt_driver'))
        if virt_driver == 'libvirt':
            self._configure_libvirt(lv.canon_libvirt_type(self._getstr('libvirt_type')), nova_conf)

        # How instances will be presented
        instance_template = self._getstr('instance_name_prefix') + self._getstr('instance_name_postfix')
        if not instance_template:
            instance_template = 'instance-%08x'
        nova_conf.add('instance_name_template', instance_template)

        # Enable the standard extensions
        nova_conf.add('osapi_compute_extension',
                      'nova.api.openstack.compute.contrib.standard_extensions')

        # Auth will be using keystone
        nova_conf.add('auth_strategy', 'keystone')

        # Don't always force images to raw
        nova_conf.add('force_raw_images', self._getbool('force_raw_images'))

        # Add a checksum for images fetched to a hypervisor
        nova_conf.add('checksum_base_images', self._getbool('checksum_base_images'))

        # Vnc settings setup
        self._configure_vnc(nova_conf)

        # Where our paste config is
        nova_conf.add('api_paste_config',
                      self.installer.target_config(PASTE_CONF))

        # What our imaging service will be
        self._configure_image_service(nova_conf, hostip)

        # Configs for ec2 / s3 stuff
        nova_conf.add('ec2_dmz_host', self._getstr('ec2_dmz_host', hostip))
        nova_conf.add('s3_host', hostip)

        # How is your message queue setup?
        mq_type = canon_mq_type(self.installer.get_option('mq'))
        if mq_type == 'rabbit':
            nova_conf.add('rabbit_host', self.cfg.getdefaulted('rabbit', 'rabbit_host', hostip))
            nova_conf.add('rabbit_password', self.cfg.get("passwords", "rabbit"))
            nova_conf.add('rabbit_userid', self.cfg.get('rabbit', 'rabbit_userid'))
            nova_conf.add('rpc_backend', 'nova.rpc.impl_kombu')

        # Where instances will be stored
        instances_path = self._getstr('instances_path', 
                                      sh.joinpths(self.installer.get_option('component_dir'), 'instances'))
        self._configure_instances_path(instances_path, nova_conf)

        # Is this a multihost setup?
        self._configure_multihost(nova_conf)

        # Handle any virt driver specifics
        self._configure_virt_driver(nova_conf)

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
            LOG.warn("EXTRA_FLAGS is defined and may need to be converted to EXTRA_OPTS!")
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

    def _configure_image_service(self, nova_conf, hostip):
        # What image service we will u be using sir?
        img_service = self._getstr('img_service', 'nova.image.glance.GlanceImageService')
        nova_conf.add('image_service', img_service)

        # If glance then where is it?
        if img_service.lower().find("glance") != -1:
            glance_api_server = self._getstr('glance_server', ("%s:9292" % (hostip)))
            nova_conf.add('glance_api_servers', glance_api_server)

    def _configure_vnc(self, nova_conf):
        # All nova-compute workers need to know the vnc configuration options
        # These settings don't hurt anything if n-xvnc and n-novnc are disabled
        nova_conf.add('novncproxy_base_url', self._getstr('vncproxy_url'))
        nova_conf.add('xvpvncproxy_base_url', self._getstr('xvpvncproxy_url'))
        nova_conf.add('vncserver_listen', self._getstr('vncserver_listen', '127.0.0.1'))
        nova_conf.add('vncserver_proxyclient_address', self._getstr('vncserver_proxyclient_address', '127.0.0.1'))

    # Fixes up your nova volumes
    def _configure_vols(self, nova_conf):
        nova_conf.add('volume_group', self._getstr('volume_group'))
        vol_name_tpl = self._getstr('volume_name_prefix') + self._getstr('volume_name_postfix')
        if not vol_name_tpl:
            vol_name_tpl = 'volume-%08x'
        nova_conf.add('volume_name_template', vol_name_tpl)
        nova_conf.add('iscsi_helper', 'tgtadm')

    def _configure_quantum(self, nova_conf):
        # TODO(harlowja) fixup for folsom
        nova_conf.add('network_api_class', 'nova.network.quantumv2.api.API')

    def _configure_network_settings(self, nova_conf):
        if self.installer.get_option('quantum'):
            self._configure_quantum(nova_conf)
        else:
            nova_conf.add('network_manager', self._getstr('network_manager'))

        # Configs dhcp bridge stuff???
        # TODO(harlowja) why is this the same as the nova.conf?
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
        nova_conf.add('flat_network_bridge', self._getstr('flat_network_bridge', 'br100'))
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
            # TODO(harlowja) need to add some goodies here
            pass
        nova_conf.add('libvirt_type', virt_type)
        nova_conf.add('libvirt_cpu_mode', 'none')

    # Configures any virt driver settings
    def _configure_virt_driver(self, nova_conf):
        drive_canon = canon_virt_driver(self._getstr('virt_driver'))
        nova_conf.add('connection_type', VIRT_DRIVER_CON_MAP.get(drive_canon, drive_canon))
        if drive_canon == 'libvirt':
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
