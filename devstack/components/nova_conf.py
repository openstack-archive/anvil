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

from devstack import component as comp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

LOG = logging.getLogger("devstack.components.nova_conf")
QUANTUM_MANAGER = 'nova.network.quantum.manager.QuantumManager'
NET_MANAGER_TEMPLATE = 'nova.network.manager.%s'
DEF_IMAGE_SERVICE = 'nova.image.glance.GlanceImageService'
DEF_SCHEDULER = 'nova.scheduler.simple.SimpleScheduler'
DEF_GLANCE_PORT = 9292

#TODO use this
QUANTUM_OPENSWITCH_OPS = [
    {
      'libvirt_vif_type': ['ethernet'],
      'libvirt_vif_driver': ['nova.virt.libvirt.vif.LibvirtOpenVswitchDriver'],
      'linuxnet_interface_driver': ['nova.network.linux_net.LinuxOVSInterfaceDriver'],
      'quantum_use_dhcp': [],
    }
]


class NovaConfigurator():
    def __init__(self, cfg, active_components):
        self.cfg = cfg
        self.active_components = active_components

    def _getbool(self, name):
        return self.cfg.getboolean('nova', name)

    def _getstr(self, name):
        return self.cfg.get('nova', name)

    def configure(self, dirs):

        #need to do this late
        from devstack.components import nova

        #TODO split up into sections??

        nova_conf = NovaConf()
        hostip = self.cfg.get('host', 'ip')

        #verbose on?
        if(self._getbool('verbose')):
            nova_conf.add_simple('verbose')

        #allow the admin api?
        if(self._getbool('allow_admin_api')):
            nova_conf.add_simple('allow_admin_api')

        #which scheduler do u want?
        scheduler = self._getstr('scheduler')
        if(not scheduler):
            scheduler = DEF_SCHEDULER
        nova_conf.add('scheduler_driver', scheduler)

        # TODO is this the right directory?
        flag_conf_fn = sh.joinpths(dirs.get('bin'), nova.API_CONF)
        nova_conf.add('dhcpbridge_flagfile', flag_conf_fn)

        #whats the network fixed range?
        nova_conf.add('fixed_range', self._getstr('fixed_range'))

        if(settings.QUANTUM in self.active_components):
            #setup quantum config
            nova_conf.add('network_manager', QUANTUM_MANAGER)
            nova_conf.add('quantum_connection_host', self.cfg.get('quantum', 'q_host'))
            nova_conf.add('quantum_connection_port', self.cfg.get('quantum', 'q_port'))
            # TODO
            #if ('q-svc' in self.othercomponents and
            #   self.cfg.get('quantum', 'q_plugin') == 'openvswitch'):
            #   self.lines.extend(QUANTUM_OPENSWITCH_OPS)
        else:
            nova_conf.add('network_manager', NET_MANAGER_TEMPLATE % (self._getstr('network_manager')))

        # TODO
        #       if ('n-vol' in self.othercomponents):
        #   self._resolve('--volume_group=', 'nova', 'volume_group')
        #   self._resolve('--volume_name_template=',
        #                 'nova', 'volume_name_prefix', '%08x')
        #   self._add('--iscsi_helper=tgtadm')

        nova_conf.add('my_ip', hostip)

        # The value for vlan_interface may default to the the current value
        # of public_interface. We'll grab the value and keep it handy.
        public_interface = self._getstr('public_interface')
        vlan_interface = self._getstr('vlan_interface')
        if(not vlan_interface):
            vlan_interface = public_interface
        nova_conf.add('public_interface', public_interface)
        nova_conf.add('vlan_interface', vlan_interface)

        #setup your sql connection and what type of virt u will be doing
        nova_conf.add('sql_connection', self.cfg.get_dbdsn('nova'))

        #configure anything libvirt releated?
        self._configure_libvirt(self._getstr('libvirt_type'), nova_conf)

        #how instances will be presented
        instance_template = (self._getstr('instance_name_prefix') +
                                self._getstr('instance_name_postfix'))
        nova_conf.add('instance_name_template', instance_template)

        if(settings.OPENSTACK_X in self.active_components):
            nova_conf.add('osapi_compute_extension', 'nova.api.openstack.compute.contrib.standard_extensions')
            nova_conf.add('osapi_compute_extension', 'extensions.admin.Admin')

        if(settings.NOVNC in self.active_components):
            vncproxy_url = self._getstr('vncproxy_url')
            if (not vncproxy_url):
                vncproxy_url = 'http://' + hostip + ':6080/vnc_auto.html'
            self.add('vncproxy_url', vncproxy_url)

        # TODO is this the right directory
        paste_conf_fn = sh.joinpths(dirs.get('bin'), nova.PASTE_CONF)
        nova_conf.add('api_paste_config', paste_conf_fn)

        img_service = self._getstr('img_service')
        if(not img_service):
            img_service = DEF_IMAGE_SERVICE
        nova_conf.add('image_service', img_service)

        ec2_dmz_host = self._getstr('ec2_dmz_host')
        if(not ec2_dmz_host):
            ec2_dmz_host = hostip
        nova_conf.add('ec2_dmz_host', ec2_dmz_host)

        #how is your rabbit setup?
        nova_conf.add('rabbit_host', self.cfg.get('default', 'rabbit_host'))
        nova_conf.add('rabbit_password', self.cfg.get("passwords", "rabbit"))

        #where is glance located?
        glance_api_server = self._getstr('glance_server')
        if(not glance_api_server):
            glance_api_server = "%s:%d" % (hostip, DEF_GLANCE_PORT)
        nova_conf.add('glance_api_servers', glance_api_server)

        #??
        nova_conf.add_simple('force_dhcp_release')

        #where instances will be stored
        instances_path = self._getstr('instances_path')
        if(instances_path):
            nova_conf.add('instances_path', instances_path)

        #is this a multihost setup?
        if(self._getbool('multi_host')):
            nova_conf.add_simple('multi_host')
            nova_conf.add_simple('send_arp_for_ha')

        #enable syslog??
        if(self.cfg.getboolean('default', 'syslog')):
            nova_conf.add_simple('use_syslog')

        #handle any virt driver specifics
        virt_driver = self._getstr('virt_driver')
        self._configure_virt_driver(virt_driver, nova_conf)

        #now make it
        conf_lines = sorted(nova_conf.generate())
        complete_file = utils.joinlinesep(*conf_lines)

        #add any extra flags in?
        extra_flags = self._getstr('extra_flags')
        if(extra_flags and len(extra_flags)):
            full_file = [complete_file, extra_flags]
            complete_file = utils.joinlinesep(*full_file)

        return complete_file

    def _configure_libvirt(self, virt_type, nova_conf):
        if(not virt_type):
            return
        nova_conf.add('libvirt_type', virt_type)

    #configures any virt driver settings
    def _configure_virt_driver(self, driver, nova_conf):
        if(not driver):
            return
        drive_canon = driver.lower().strip()
        if(drive_canon == 'xenserver'):
            nova_conf.add('connection_type', 'xenapi')
            nova_conf.add('xenapi_connection_url', 'http://169.254.0.1')
            nova_conf.add('xenapi_connection_username', 'root')
            nova_conf.add('xenapi_connection_password', self.cfg.get("passwords", "xenapi_connection"))
            nova_conf.add_simple('noflat_injected')
            nova_conf.add('flat_interface', 'eth1')
            nova_conf.add('flat_network_bridge', 'xapi1')
        else:
            nova_conf.add('flat_network_bridge', self._getstr('flat_network_bridge'))
            nova_conf.add('flat_interface', self._getstr('flat_interface'))


class NovaConf():
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
        if(has_opts):
            key_str += "="
        return key_str

    def generate(self, param_dict=None):
        gen_lines = list()
        for line_entry in self.lines:
            key = line_entry.get('key')
            opts = line_entry.get('options')
            if(not key or len(key) == 0):
                continue
            if(opts == None):
                key_str = self._form_key(key, False)
                full_line = key_str
            else:
                key_str = self._form_key(key, len(opts))
                filled_opts = list()
                for opt in opts:
                    filled_opts.append(utils.param_replace(str(opt), param_dict))
                full_line = key_str + ",".join(filled_opts)
            gen_lines.append(full_line)
        return gen_lines
