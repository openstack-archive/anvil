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

import os
from devstack import component as comp
from devstack import log as logging
from devstack import settings
from devstack import utils
from devstack import shell as sh
from devstack.components import db

LOG = logging.getLogger('devstack.components.nova')

#config files adjusted
API_CONF = 'nova.conf'
CONFIGS = [API_CONF]

#config just referenced
PASTE_CONF = 'nova-api-paste.ini'

#this db will be dropped then created
DB_NAME = 'nova'

#id
TYPE = settings.NOVA

#what to start
APP_OPTIONS = {
    'nova-api': ['--flagfile', '%CFGFILE%'],
    settings.NCPU: ['--flagfile', '%CFGFILE%'],
    settings.NVOL: ['--flagfile', '%CFGFILE%'],
    'nova-network': ['--flagfile', '%CFGFILE%'],
    'nova-scheduler': ['--flagfile', '%CFGFILE%']
}

#post install cmds that will happen after install
POST_INSTALL_CMDS = [
    {'cmd': ['%BINDIR%nova-manage', '--flagfile', '%CFGFILE%',
             'db', 'sync']},
    {'cmd': ['%BINDIR%nova-manage', '--flagfile', '%CFGFILE%',
              'floating', 'create', '%FLOATING_RANGE%']},
    {'cmd': ['%BINDIR%nova-manage', '--flagfile', '%CFGFILE%',
              'floating', 'create', '--ip_range=%TEST_FLOATING_RANGE%',
              '--pool=%TEST_FLOATING_POOL%']}
]

# In case we need to map names to the image to run
APP_NAME_MAP = {
    settings.NCPU: 'nova-compute',
    settings.NVOL: 'nova-volume',
}

#subdirs of the checkout/download
BIN_DIR = 'bin'

#These are used by NovaConf
QUANTUM_MANAGER = 'nova.network.quantum.manager.QuantumManager'
NET_MANAGER_TEMPLATE = 'nova.network.manager.%s'
DEF_IMAGE_SERVICE = 'nova.image.glance.GlanceImageService'
DEF_SCHEDULER = 'nova.scheduler.simple.SimpleScheduler'
DEF_GLANCE_PORT = 9292

QUANTUM_OPENSWITCH_OPS = [
    {
      'libvirt_vif_type': ['ethernet'],
      'libvirt_vif_driver': ['nova.virt.libvirt.vif.LibvirtOpenVswitchDriver'],
      'linuxnet_interface_driver': ['nova.network.linux_net.LinuxOVSInterfaceDriver'],
      'quantum_use_dhcp': [],
    }
]


class NovaUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)


class NovaInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.git_repo = self.cfg.get("git", "nova_repo")
        self.git_branch = self.cfg.get("git", "nova_branch")
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)

    def get_pkglist(self):
        pkgs = comp.PkgInstallComponent.get_pkglist(self)
        # Walk through the subcomponents (like 'vol' and 'cpu') and add those
        # those packages as well. (Let utils.get_pkglist handle any missing
        # entries
        LOG.debug("get_pkglist looking for extras: %s" % (self.component_opts))
        for cname in self.component_opts:
            pkgs.update(utils.get_pkg_list(self.distro, cname))
        return pkgs

    def _get_download_locations(self):
        places = comp.PythonInstallComponent._get_download_locations(self)
        places.append({
            'uri': self.git_repo,
            'branch': self.git_branch,
        })
        return places

    def _get_config_files(self):
        return list(CONFIGS)

    def post_install(self):
        parent_result = comp.PkgInstallComponent.post_install(self)
        LOG.debug("Parent post_install results:%s" % (parent_result))
        #extra actions to do nova setup
        self._setup_db()
        # Need to do db sync and other post install commands
        # set up replacement map for CFGFILE, BINDIR, FLOATING_RANGE,
        # TEST_FLOATING_RANGE, TEST_FLOATING_POOL
        mp = dict()
        mp['BINDIR'] = self.bindir + os.sep
        mp['CFGFILE'] = self.cfgdir + os.sep + API_CONF
        mp['FLOATING_RANGE'] = self.cfg.get('nova', 'floating_range')
        mp['TEST_FLOATING_RANGE'] = self.cfg.get('nova', 'test_floating_range')
        mp['TEST_FLOATING_POOL'] = self.cfg.get('nova', 'test_floating_pool')
        utils.execute_template(*POST_INSTALL_CMDS, params=mp, tracewriter=self.tracewriter)
        return parent_result

    def _setup_db(self):
        LOG.debug("setting up nova DB")
        db.drop_db(self.cfg, DB_NAME)
        db.create_db(self.cfg, DB_NAME)

    def _generate_nova_conf(self):
        LOG.debug("Generating dynamic content for nova configuration")
        dirs = dict()
        dirs['app'] = self.appdir
        dirs['cfg'] = self.cfgdir
        dirs['bin'] = self.bindir
        conf_gen = NovaConfigurator(self.cfg, self.instances)
        nova_conf = conf_gen.configure(dirs)
        tgtfn = self._get_target_config_name(API_CONF)
        LOG.info("Writing conf to %s" % (tgtfn))
        LOG.info(nova_conf)
        sh.write_file(tgtfn, nova_conf)
        #we configured one file, return that we did that
        return 1

    def _configure_files(self):
        return self._generate_nova_conf()


class NovaRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, TYPE, *args, **kargs)
        self.run_tokens = dict()
        self.run_tokens['CFGFILE'] = self.cfgdir + os.sep + API_CONF
        LOG.debug("Setting CFGFILE run_token to:%s" % (self.run_tokens['CFGFILE']))

    def _get_aps_to_start(self):
        # Check if component_opts was set to a subset of apps to be started
        apps = list()
        if not self.component_opts and len(self.component_opts) > 0:
            LOG.debug("Attempt to use subset of components:%s" % (self.component_opts))
            # check if the specified sub components exist
            delta = set(self.component_opts) - set(APP_OPTIONS.keys())
            if delta:
                # FIXME, error, something was specified that we don't have
                LOG.error("sub items that we don't know about:%s" % delta)
            else:
                apps = self.component_opts
                LOG.debug("Using specified subcomponents:%s" % (apps))
        else:
            apps = APP_OPTIONS.keys()
            LOG.debug("Using the keys from APP_OPTIONS:%s" % (apps))

        result = list()
        for app_name in apps:
            if app_name in APP_NAME_MAP:
                app_name = APP_NAME_MAP.get(app_name)
                LOG.debug("Renamed app_name to:" + app_name)
            list.append({
                'name': app_name,
                'path': sh.joinpths(self.appdir, BIN_DIR, app_name),
            })
        LOG.debug("exiting _get_aps_to_start with:%s" % (result))
        return result

    def _get_app_options(self, app):
        result = list()
        for opt_str in APP_OPTIONS.get(app):
            LOG.debug("Checking opt_str for tokens: %s" % (opt_str))
            result.append(utils.param_replace(opt_str, self.run_tokens))

        LOG.debug("_get_app_options returning with:%s" % (result))
        return result


# This class has the smarts to build the configuration file based on
# various runtime values
class NovaConfigurator(object):
    def __init__(self, cfg, instances):
        self.cfg = cfg
        self.instances = instances

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

        flag_conf_fn = sh.joinpths(dirs.get('bin'), API_CONF)
        nova_conf.add('dhcpbridge_flagfile', flag_conf_fn)

        #whats the network fixed range?
        nova_conf.add('fixed_range', self._getstr('fixed_range'))

        if settings.QUANTUM in self.instances:
            #setup quantum config
            nova_conf.add('network_manager', QUANTUM_MANAGER)
            nova_conf.add('quantum_connection_host', self.cfg.get('quantum', 'q_host'))
            nova_conf.add('quantum_connection_port', self.cfg.get('quantum', 'q_port'))
            # TODO add q-svc support
            #if 'q-svc' in self.othercomponents and
            #   self.cfg.get('quantum', 'q_plugin') == 'openvswitch':
            #   self.lines.extend(QUANTUM_OPENSWITCH_OPS)
        else:
            nova_conf.add('network_manager', NET_MANAGER_TEMPLATE % (self._getstr('network_manager')))

        # TODO add n-vol support
        #       if 'n-vol' in self.othercomponents:
        #   self._resolve('--volume_group=', 'nova', 'volume_group')
        #   self._resolve('--volume_name_template=',
        #                 'nova', 'volume_name_prefix', '%08x')
        #   self._add('--iscsi_helper=tgtadm')

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
        instance_template = (self._getstr('instance_name_prefix') +
                                self._getstr('instance_name_postfix'))
        nova_conf.add('instance_name_template', instance_template)

        if settings.OPENSTACK_X in self.instances:
            nova_conf.add('osapi_compute_extension', 'nova.api.openstack.compute.contrib.standard_extensions')
            nova_conf.add('osapi_compute_extension', 'extensions.admin.Admin')

        if settings.NOVNC in self.instances:
            vncproxy_url = self._getstr('vncproxy_url')
            if not vncproxy_url:
                vncproxy_url = 'http://' + hostip + ':6080/vnc_auto.html'
            nova_conf.add('vncproxy_url', vncproxy_url)

        paste_conf_fn = sh.joinpths(dirs.get('bin'), PASTE_CONF)
        nova_conf.add('api_paste_config', paste_conf_fn)

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
        if instances_path:
            nova_conf.add('instances_path', instances_path)

        #is this a multihost setup?
        if self._getbool('multi_host'):
            nova_conf.add_simple('multi_host')
            nova_conf.add_simple('send_arp_for_ha')

        #enable syslog??
        if self.cfg.getboolean('default', 'syslog'):
            nova_conf.add_simple('use_syslog')

        #handle any virt driver specifics
        virt_driver = self._getstr('virt_driver')
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
            nova_conf.add('flat_network_bridge', 'xapi1')
        else:
            nova_conf.add('connection_type', self._getstr('connection_type'))
            nova_conf.add('flat_network_bridge', self._getstr('flat_network_bridge'))
            nova_conf.add('flat_interface', self._getstr('flat_interface'))


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
