# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import Logger

QUANTUM_OPENSWITCH_OPS = [
  '--libvirt_vif_type=ethernet', 
  '--libvirt_vif_driver=nova.virt.libvirt.vif.LibvirtOpenVswitchDriver',
  '--linuxnet_interface_driver=nova.network.linux_net.LinuxOVSInterfaceDriver',
  '--quantum_use_dhcp']

OS_EXTENSIONS = [
  '--osapi_compute_extension='
    'nova.api.openstack.compute.contrib.standard_extensions',
  '--osapi_compute_extension=extensions.admin.Admin']

MULTI_HOST_OPS = [ '--multi_host', '--send_arp_for_ha']

class NovaConf:
    # Our accumlator for lines that will go into nova.conf
    lines = []

    # We should be passed the config object that holds all the values we need
    def __init__(self, nova_component):
       # Get handles to info from the main Nova component that we'll need
       self.cfg  = nova_component.cfg
       self.othercomponents = nova_component.othercomponents

    # Add a line to the output that contains one value from the config
    def _resolve(self, prefix, section, variable, postfix = ''):
        value = self.cfg.get(section, variable)
        self._add(prefix + value + postfix)

    # Just a convience method to have the list appending in one place
    def _add(self, ldata):
        self.lines.append(ldata)

    def generate(self):
        self.lines = []
        self._add('--verbose')
        self._add('--allow_admin_api')
        self._resolve('--scheduler_driver=', 'nova', 'scheduler')
        nova_dir = self.appdir   # FIXME, is this correct? 
        self._add('--dhcpbridge_flagfile=' + nova_dir + '/bin/nova.conf')
        self._resolve('--fixed_range=', 'nova', 'fixed_range')

        # Check if quantum is enabled, and if so, add all the necessary 
        # config magic that goes with it
        if (QUANTUM in self.othercomponents):
            # Set network manager to multi lines
            self._add(
               '--network_manager=nova.network.quantum.manager.QuantumManager')
            self._add(
               '--network_manager=nova.network.quantum.manager.QuantumManager')
            self._resolve('--quantum_connection_host=', 'quantum', 'q_host')
            self._resolve('--quantum_connection_port=', 'quantum', 'q_port')
            if ('q-svc' in self.othercomponents and 
                self.cfg.get('quantum', 'q_plugin') == 'openvswitch'):
                self.lines.extend(QUANTUM_OPENSWITCH_OPS)
        else:
            self._resolve('--network_manager=nova.network.manager.', 
                          'nova', 'network_manager')
        if ('n-vol' in self.othercomponents):
            self._resolve('--volume_group=', 'nova', 'volume_group')
            self._resolve('--volume_name_template=', 
                          'nova', 'volume_name_prefix', '%08x')
            self._add('--iscsi_helper=tgtadm')

        # FIXME, I think this from Component
        hostip = get_host_ip(self.cfg)
        self._add('--my_ip=' + hostip)

        # The value for vlan_interface may default to the the current value
        # of public_interface. We'll grab the value and keep it handy
        public_interface = self.cfg.get("nova", "public_interface")
        vlan_interface = self.cfg.get("nova", "vlan_interface");
        if (vlan_interface == ''):
            vlan_interface = public_interface
        self._add('--public_interface=' + public_interface)
        self._add('--vlan_interface=' + vlan_interface)
        self._add('--sql_connection=' + self.cfg.get_dbdsn('nova'))
        self._resolve('--libvirt_type=', 'nova', 'libvirt_type')
        self._resolve('--instance_name_template=', 
                      'nova', 'instance_name_prefix', '%08x')
        if ('openstackx' in self.othercomponents):
            self.lines.extend(OS_EXTENSIONS)

        if ('n-vnc' in self.othercomponents):
            vncproxy_url = self.cfg.get("nova", "vncproxy_url")
            if (vncproxy_url == ''):
                vncproxy_url = 'http://' + hostip + ':6080' 
            self._add('--vncproxy_url=' + vncproxy_url)
            self._add('vncproxy_wwwroot=' + nova_dir + '/')

        self._add('--api_paste_config=' + nova_dir + '/bin/nova-api-paste.ini')
        self._add('--image_service=nova.image.glance.GlanceImageService')
        ec2_dmz_host = self.cfg.get("nova", "ec2_dmz_host")
        if (ec2_dmz_host == ''):
            ec2_dmz_host = hostip
        self._add('--ec2_dmz_host=' + ec2_dmz_host) 
        self._resolve('--rabbit_host=', 'default', 'rabbit_host')
        self._add('--rabbit_password=' + self.cfg.getpw("passwords", "rabbit"))
        self._add('--glance_api_servers=' + hostip + ':9292')
        self._add('--force_dhcp_release')

        instances_path = self.cfg.get("nova", "instances_path")
        if (instances_path != ''):
	    self._add('--instances_path=' + instances_path)

        multi_host = self.cfg.getboolean("nova", "multi_host")
        if (multi_host == true):
            self.lines.extend(MULTI_HOST_OPS) 
            
	if (self.cfg.getboolean("default", "syslog")) :
	    self._add('--use_syslog')

        extra_flags = self.cfg.get("nova", "extra_flags") 
	if (extra_flags != ''):
	    # FIXME, this is assuming that multiple flags are newline delimited 
	    self._add(extra_flags)

        virt_driver = self.cfg.get("nova", "virt_driver")
        if (virt_driver == 'xenserver'):
            self.add('--connection_type=xenapi')
            self.add('--xenapi_connection_url=http://169.254.0.1')
            self.add('--xenapi_connection_username=root')
            # TBD, check that this is the right way to get the password
            self.add('--xenapi_connection_password=' +
                          self.cfg.getpw("passwords", "xenapi"))
            self.add('--noflat_injected')
            self.add('--flat_interface=eth1')
            self.addappend('--flat_network_bridge=xapi1')
	else:
	    self.resolve('--flat_network_bridge=', 
	                 'nova', 'flat_network_bridge') 
	    self.resolve('--flat_interface=', 'nova', 'flat_interface') 
        return self.lines
