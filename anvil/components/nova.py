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

from anvil import colorizer
from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.components import base_install as binstall
from anvil.components import base_runtime as bruntime

from anvil.components.configurators import nova as nconf
from anvil.components.helpers import nova as nhelper
from anvil.components.helpers import virt as lv

LOG = logging.getLogger(__name__)

# This is a special marker file that when it exists, signifies that nova net was inited
NET_INITED_FN = 'nova.network.inited.yaml'

# This makes the database be in sync with nova
DB_SYNC_CMD = [
    {'cmd': ['sudo', '-u', 'nova', '/usr/bin/nova-manage', 'db', 'sync']},
]

# Used to create a fixed network when initializating nova
FIXED_NET_CMDS = [
    {
        'cmd': ['sudo', '-u', 'nova', '/usr/bin/nova-manage',
                'network', 'create', 'private', '$FIXED_RANGE', '1', '$FIXED_NETWORK_SIZE'],
    },
]

# Used to create a floating network + test floating pool
FLOATING_NET_CMDS = [
    {
        'cmd': ['sudo', '-u', 'nova', '/usr/bin/nova-manage',
                'floating', 'create', '$FLOATING_RANGE'],
    },
    {
        'cmd': ['sudo', '-u', 'nova', '/usr/bin/nova-manage',
                'floating', 'create', '--ip_range=$TEST_FLOATING_RANGE', '--pool=$TEST_FLOATING_POOL'],
    },
]


class NovaUninstaller(binstall.PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        binstall.PkgUninstallComponent.__init__(self, *args, **kargs)
        self.virsh = lv.Virsh(self.get_int_option('service_wait_seconds'), self.distro)
        self.net_init_fn = sh.joinpths(self.get_option('trace_dir'), NET_INITED_FN)

    def pre_uninstall(self):
        if 'compute' in self.subsystems:
            self._clean_compute()
        if 'network' in self.subsystems:
            self._clean_net()

    def unconfigure(self):
        if sh.isfile(self.net_init_fn):
            sh.unlink(self.net_init_fn)

    def _clean_net(self):
        try:
            LOG.info("Cleaning up nova-network's dirty laundry.")
            cleaner = nhelper.NetworkCleaner(self)
            cleaner.clean()
        except Exception as e:
            LOG.warn("Failed cleaning up nova-network's dirty laundry due to: %s", e)

    def _clean_compute(self):
        try:
            LOG.info("Cleaning up nova-compute's dirty laundry.")
            cleaner = nhelper.ComputeCleaner(self)
            cleaner.clean()
        except Exception as e:
            LOG.warn("Failed cleaning up nova-compute's dirty laundry due to: %s", e)


class NovaInstaller(binstall.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        binstall.PythonInstallComponent.__init__(self, *args, **kargs)
        self.configurator = nconf.NovaConfigurator(self)

    @property
    def env_exports(self):
        to_set = utils.OrderedDict()
        to_set['OS_COMPUTE_API_VERSION'] = self.get_option('nova_version')
        n_params = nhelper.get_shared_params(**self.options)
        for (endpoint, details) in n_params['endpoints'].items():
            to_set[("NOVA_%s_URI" % (endpoint.upper()))] = details['uri']
        return to_set

    def verify(self):
        binstall.PythonInstallComponent.verify(self)
        self.configurator.verify()

    def _sync_db(self):
        LOG.info("Syncing nova to database named: %s", colorizer.quote(self.configurator.DB_NAME))
        utils.execute_template(*DB_SYNC_CMD, params=self.config_params(None))

    def _fix_virt(self):
        virt_driver = utils.canon_virt_driver(self.get_option('virt_driver'))
        if virt_driver == 'libvirt':
            virt_type = lv.canon_libvirt_type(self.get_option('libvirt_type'))
            if virt_type == 'qemu':
                # On RHEL it appears a sym-link needs to be created
                # to enable qemu to actually work, apparently fixed
                # in RHEL 6.4.
                #
                # See: http://fedoraproject.org/wiki/Getting_started_with_OpenStack_EPEL
                if not sh.isfile('/usr/bin/qemu-system-x86_64'):
                    sh.symlink('/usr/libexec/qemu-kvm', '/usr/bin/qemu-system-x86_64',
                               tracewriter=self.tracewriter)

    def post_install(self):
        binstall.PythonInstallComponent.post_install(self)
        # Extra actions to do nova setup
        if self.get_bool_option('db-sync'):
            self.configurator.setup_db()
            self._sync_db()
        # Patch up your virtualization system
        self._fix_virt()


class NovaRuntime(bruntime.OpenStackRuntime):
    def __init__(self, *args, **kargs):
        bruntime.OpenStackRuntime.__init__(self, *args, **kargs)
        self.wait_time = self.get_int_option('service_wait_seconds')
        self.virsh = lv.Virsh(self.wait_time, self.distro)
        self.net_init_fn = sh.joinpths(self.get_option('trace_dir'), NET_INITED_FN)

    def _do_network_init(self):
        if not sh.isfile(self.net_init_fn) and self.get_bool_option('do-network-init'):
            # Figure out the commands to run
            cmds = []
            mp = {}
            if self.get_bool_option('enable_fixed'):
                # Create a fixed network
                mp['FIXED_NETWORK_SIZE'] = self.get_option('fixed_network_size', default_value='256')
                mp['FIXED_RANGE'] = self.get_option('fixed_range', default_value='10.0.0.0/24')
                cmds.extend(FIXED_NET_CMDS)
            if self.get_bool_option('enable_floating'):
                # Create a floating network + test floating pool
                cmds.extend(FLOATING_NET_CMDS)
                mp['FLOATING_RANGE'] = self.get_option('floating_range', default_value='172.24.4.224/28')
                mp['TEST_FLOATING_RANGE'] = self.get_option('test_floating_range', default_value='192.168.253.0/29')
                mp['TEST_FLOATING_POOL'] = self.get_option('test_floating_pool', default_value='test')
            # Anything to run??
            if cmds:
                LOG.info("Creating your nova network to be used with instances.")
                utils.execute_template(*cmds, params=mp)
            # Writing this makes sure that we don't init again
            cmd_mp = {
                'cmds': cmds,
                'replacements': mp,
            }
            sh.write_file(self.net_init_fn, utils.prettify_yaml(cmd_mp))
            LOG.info("If you wish to re-run network initialization, delete %s", colorizer.quote(self.net_init_fn))

    def post_start(self):
        self._do_network_init()

    def pre_start(self):
        # Let the parent class do its thing
        bruntime.OpenStackRuntime.pre_start(self)
        virt_driver = utils.canon_virt_driver(self.get_option('virt_driver'))
        if virt_driver == 'libvirt':
            virt_type = lv.canon_libvirt_type(self.get_option('libvirt_type'))
            LOG.info("Checking that your selected libvirt virtualization type %s is working and running.", colorizer.quote(virt_type))
            try:
                self.virsh.check_virt(virt_type)
                self.virsh.restart_service()
                LOG.info("Libvirt virtualization type %s seems to be working and running.", colorizer.quote(virt_type))
            except excp.ProcessExecutionError as e:
                msg = ("Libvirt type %r does not seem to be active or configured correctly, "
                        "perhaps you should be using %r instead: %s" %
                        (virt_type, lv.DEF_VIRT_TYPE, e))
                raise excp.StartException(msg)
