# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2013 Yahoo! Inc. All Rights Reserved.
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

from anvil import exceptions
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.components.helpers import neutron as net_helper
from anvil.components.helpers import virt as lv

from anvil.components.configurators import base

API_CONF = 'nova.conf'
PASTE_CONF = 'nova-api-paste.ini'
POLICY_CONF = 'policy.json'
LOGGING_CONF = "logging.conf"
CONFIGS = [PASTE_CONF, POLICY_CONF, LOGGING_CONF, API_CONF]
MQ_BACKENDS = {
    'qpid': 'nova.rpc.impl_qpid',
    'rabbit': 'nova.rpc.impl_kombu',
}

LOG = logging.getLogger(__name__)


class NovaConfigurator(base.Configurator):

    # This db will be dropped then created
    DB_NAME = 'nova'

    def __init__(self, installer):
        super(NovaConfigurator, self).__init__(installer, CONFIGS)
        self.config_adjusters = {PASTE_CONF: self._config_adjust_paste,
                                 API_CONF: self._config_adjust_api,
                                 LOGGING_CONF: self._config_adjust_logging}
        self.source_configs = {PASTE_CONF: 'api-paste.ini',
                               LOGGING_CONF: 'logging_sample.conf',
                               API_CONF: 'nova.conf.sample'}
        self.tracewriter = self.installer.tracewriter
        self.config_dir = sh.joinpths(self.installer.get_option('app_dir'),
                                      'etc',
                                      installer.name)

    def _config_adjust_paste(self, config):
        for (k, v) in self._fetch_keystone_params().items():
            config.add_with_section('filter:authtoken', k, v)

    def _config_adjust_api(self, nova_conf):
        '''This method has the smarts to build the configuration file based on
           various runtime values. A useful reference for figuring out this
           is at http://docs.openstack.org/diablo/openstack-compute/admin/content/ch_configuring-openstack-compute.html
           See also: https://github.com/openstack/nova/blob/master/etc/nova/nova.conf.sample
        '''

        # Used more than once so we calculate it ahead of time
        hostip = self.installer.get_option('ip')

        nova_conf.add('verbose', self.installer.get_bool_option('log_verbose'))
        nova_conf.add('state_path', '/var/lib/nova')
        nova_conf.add('log_dir', '/var/log/nova')
        nova_conf.add('bindir', '/usr/bin')

        # Allow destination machine to match source for resize.
        nova_conf.add('allow_resize_to_same_host', True)

        # Which scheduler do u want?
        nova_conf.add('compute_scheduler_driver',
                      self.installer.get_option('scheduler', default_value='nova.scheduler.filter_scheduler.FilterScheduler'))

        # Rate limit the api??
        nova_conf.add('api_rate_limit', self.installer.get_bool_option('api_rate_limit'))

        # Ensure the policy.json is referenced correctly
        nova_conf.add('policy_file', '/etc/nova/policy.json')

        # Setup nova network/settings
        self._configure_network_settings(nova_conf)

        # The ip of where we are running
        nova_conf.add('my_ip', hostip)

        # Setup how the database will be connected.
        nova_conf.add('sql_connection', self.fetch_dbdsn())

        # Configure anything libvirt related?
        virt_driver = utils.canon_virt_driver(self.installer.get_option('virt_driver'))
        if virt_driver == 'libvirt':
            self._configure_libvirt(lv.canon_libvirt_type(self.installer.get_option('libvirt_type')), nova_conf)

        # How instances will be presented
        instance_template = "%s%s" % (self.installer.get_option('instance_name_prefix'),
                                      self.installer.get_option('instance_name_postfix'))
        if not instance_template:
            instance_template = 'instance-%08x'
        nova_conf.add('instance_name_template', instance_template)

        # Enable the standard extensions
        nova_conf.add('osapi_compute_extension',
                      'nova.api.openstack.compute.contrib.standard_extensions')

        # Auth will be using keystone
        nova_conf.add('auth_strategy', 'keystone')

        # Is config drive being forced on?
        if self.installer.get_bool_option('force_cfg_drive'):
            nova_conf.add('force_config_drive', 'always')

        # Don't always force images to raw, which makes things take time to get to raw...
        nova_conf.add('force_raw_images', self.installer.get_bool_option('force_raw_images'))

        # Add a checksum for images fetched for each hypervisor?
        # This check absorbs cpu cycles, warning....
        nova_conf.add('checksum_base_images', self.installer.get_bool_option('checksum_base_images'))

        # Setup the interprocess locking directory (don't put me on shared storage)
        nova_conf.add('lock_path', '/var/lock/nova')

        # Vnc settings setup
        self._configure_vnc(nova_conf)

        # Where our paste config is
        nova_conf.add('api_paste_config', self.target_config(PASTE_CONF))

        # What our imaging service will be
        self._configure_image_service(nova_conf, hostip)

        # Configs for ec2 / s3 stuff
        nova_conf.add('ec2_dmz_host', self.installer.get_option('ec2_dmz_host', default_value=hostip))
        nova_conf.add('s3_host', hostip)

        # How is your message queue setup?
        self.setup_rpc(nova_conf, rpc_backends=MQ_BACKENDS)

        # The USB tablet device is meant to improve mouse behavior in
        # the VNC console, but it has the side effect of increasing
        # the CPU usage of an idle VM tenfold.
        nova_conf.add('use_usb_tablet', False)

        # Is this a multihost setup?
        self._configure_multihost(nova_conf)

        # Handle any virt driver specifics
        self._configure_virt_driver(nova_conf)

        # Handle configuring the conductor service
        self._configure_conductor(nova_conf)

    def _config_adjust_logging(self, config):
        config.add_with_section('logger_root', 'level', 'DEBUG')
        config.add_with_section('logger_root', 'handlers', "stdout")

    def _fetch_keystone_params(self):
        params = self.get_keystone_params('nova')
        return {
            'auth_host': params['endpoints']['admin']['host'],
            'auth_port': params['endpoints']['admin']['port'],
            'auth_protocol': params['endpoints']['admin']['protocol'],

            'admin_tenant_name': params['service_tenant'],
            'admin_user': params['service_user'],
            'admin_password': params['service_password'],

            'service_host': params['endpoints']['internal']['host'],
            'service_port': params['endpoints']['internal']['port'],
            'service_protocol': params['endpoints']['internal']['protocol'],
        }

    def _get_extra(self, key):
        extras = self.installer.get_option(key)
        if not extras:
            return []
        cleaned_lines = []
        extra_lines = str(extras).splitlines()
        for line in extra_lines:
            cleaned_line = line.strip()
            if cleaned_line:
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
        img_service = self.installer.get_option('img_service', default_value='nova.image.glance.GlanceImageService')
        nova_conf.add('image_service', img_service)

        # If glance then where is it?
        if img_service.lower().find("glance") != -1:
            glance_api_server = self.installer.get_option('glance_server', default_value=("%s:9292" % (hostip)))
            nova_conf.add('glance_api_servers', glance_api_server)

    def _configure_vnc(self, nova_conf):
        # All nova-compute workers need to know the vnc configuration options
        # These settings don't hurt anything if n-xvnc and n-novnc are disabled
        nova_conf.add('novncproxy_base_url', self.installer.get_option('vncproxy_url'))
        nova_conf.add('xvpvncproxy_base_url', self.installer.get_option('xvpvncproxy_url'))
        nova_conf.add('vncserver_listen', self.installer.get_option('vncserver_listen', default_value='127.0.0.1'))
        nova_conf.add('vncserver_proxyclient_address', self.installer.get_option('vncserver_proxyclient_address', default_value='127.0.0.1'))

    def _configure_neutron(self, nova_conf):
        params = self.get_keystone_params('nova')
        params['neutron'] = net_helper.get_shared_params(
            ip=self.installer.get_option('ip'),
            **self.installer.get_option('neutron'))

        nova_conf.add("network_api_class", "nova.network.neutronv2.api.API")
        nova_conf.add("neutron_admin_username", params['service_user'])
        nova_conf.add("neutron_admin_password", params['service_password'])
        nova_conf.add("neutron_admin_auth_url", params['endpoints']['admin']['uri'])
        nova_conf.add("neutron_auth_strategy", "keystone")
        nova_conf.add("neutron_admin_tenant_name", params['service_tenant'])
        nova_conf.add("neutron_url", params['neutron']['endpoints']['admin']['uri'])
        libvirt_vif_drivers = {
            "linuxbridge": "nova.virt.libvirt.vif.NeutronLinuxBridgeVIFDriver",
            "openvswitch": "nova.virt.libvirt.vif.LibvirtHybridOVSBridgeDriver",
        }
        # FIXME(aababilov): error on KeyError
        nova_conf.add(
            "libvirt_vif_driver",
            libvirt_vif_drivers[self.installer.get_option('neutron-core-plugin')])

        # FIXME(aababilov): add for linuxbridge:
        nova_conf.add("libvirt_vif_type", "ethernet")
        nova_conf.add("connection_type", "libvirt")
        nova_conf.add("neutron_use_dhcp",
                      self.installer.get_bool_option('neutron-use-dhcp'))

    def _configure_cells(self, nova_conf):
        cells_enabled = self.installer.get_bool_option('enable-cells')
        nova_conf.add_with_section('cells', 'enable', cells_enabled)

    def _configure_spice(self, nova_conf):
        spicy = self.installer.get_bool_option('enable-spice')
        nova_conf.add_with_section('spice', 'enable', spicy)

    def _configure_conductor(self, nova_conf):
        conductor_local = self.installer.get_bool_option('local-conductor')
        nova_conf.add_with_section('conductor', 'use_local', conductor_local)

    def _configure_network_settings(self, nova_conf):
        if self.installer.get_bool_option('neutron-enabled'):
            self._configure_neutron(nova_conf)
        else:
            nova_conf.add('network_manager', self.installer.get_option('network_manager'))

        # Configs dhcp bridge stuff???
        # TODO(harlowja) why is this the same as the nova.conf?
        nova_conf.add('dhcpbridge_flagfile', sh.joinpths(self.installer.cfg_dir, API_CONF))

        # Network prefix for the IP network that all the projects for future VM guests reside on. Example: 192.168.0.0/12
        nova_conf.add('fixed_range', self.installer.get_option('fixed_range'))

        # The value for vlan_interface may default to the the current value
        # of public_interface. We'll grab the value and keep it handy.
        public_interface = self.installer.get_option('public_interface')
        vlan_interface = self.installer.get_option('vlan_interface', default_value=public_interface)
        nova_conf.add('public_interface', public_interface)
        nova_conf.add('vlan_interface', vlan_interface)

        # This forces dnsmasq to update its leases table when an instance is terminated.
        nova_conf.add('force_dhcp_release', True)

        # Special virt driver network settings
        nova_conf.add('flat_network_bridge', self.installer.get_option('flat_network_bridge', default_value='br100'))
        nova_conf.add('flat_injected', self.installer.get_bool_option('flat_injected'))
        flat_interface = self.installer.get_option('flat_interface')
        if flat_interface:
            nova_conf.add('flat_interface', flat_interface)

    # Enables multihost (??)
    def _configure_multihost(self, nova_conf):
        if self.installer.get_bool_option('multi_host'):
            nova_conf.add('multi_host', True)
            nova_conf.add('send_arp_for_ha', True)

    # Any special libvirt configurations go here
    def _configure_libvirt(self, virt_type, nova_conf):
        nova_conf.add('libvirt_type', virt_type)
        # https://blueprints.launchpad.net/nova/+spec/libvirt-xml-cpu-model
        nova_conf.add('libvirt_cpu_mode', 'none')

    # Configures any virt driver settings
    def _configure_virt_driver(self, nova_conf):
        drive_canon = utils.canon_virt_driver(self.installer.get_option('virt_driver'))
        nova_conf.add('compute_driver', utils.VIRT_DRIVER_MAP.get(drive_canon, drive_canon))
        if drive_canon == 'libvirt':
            nova_conf.add('firewall_driver', self.installer.get_option('libvirt_firewall_driver'))
        else:
            nova_conf.add('firewall_driver', self.installer.get_option('basic_firewall_driver'))

    def verify(self):
        # Do a little check to make sure actually have that interface/s
        public_interface = self.installer.get_option('public_interface')
        vlan_interface = self.installer.get_option('vlan_interface', default_value=public_interface)
        known_interfaces = utils.get_interfaces()
        if public_interface not in known_interfaces:
            msg = "Public interface %r is not a known interface (is it one of %s??)" % (public_interface, ", ".join(known_interfaces))
            raise exceptions.ConfigException(msg)
        if vlan_interface not in known_interfaces:
            msg = "VLAN interface %r is not a known interface (is it one of %s??)" % (vlan_interface, ", ".join(known_interfaces))
            raise exceptions.ConfigException(msg)
        # Driver specific interface checks
        drive_canon = utils.canon_virt_driver(self.installer.get_option('virt_driver'))
        if drive_canon == 'libvirt':
            flat_interface = self.installer.get_option('flat_interface')
            if flat_interface and flat_interface not in known_interfaces:
                msg = "Libvirt flat interface %s is not a known interface (is it one of %s??)" % (flat_interface, ", ".join(known_interfaces))
                raise exceptions.ConfigException(msg)
