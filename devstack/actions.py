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

from devstack import constants as c

from devstack.components import db
from devstack.components import glance
from devstack.components import horizon
from devstack.components import keystone
from devstack.components import keystone_client
from devstack.components import nova
from devstack.components import nova_client
from devstack.components import openstack_x
from devstack.components import quantum
from devstack.components import rabbit
from devstack.components import swift


# This determines what classes to use to install/uninstall/...
ACTION_CLASSES = {
    c.INSTALL: {
        c.NOVA: nova.NovaInstaller,
        c.GLANCE: glance.GlanceInstaller,
        c.QUANTUM: quantum.QuantumInstaller,
        c.SWIFT: swift.SwiftInstaller,
        c.HORIZON: horizon.HorizonInstaller,
        c.KEYSTONE: keystone.KeystoneInstaller,
        c.DB: db.DBInstaller,
        c.RABBIT: rabbit.RabbitInstaller,
        c.KEYSTONE_CLIENT: keystone_client.KeyStoneClientInstaller,
        c.NOVA_CLIENT: nova_client.NovaClientInstaller,
        c.OPENSTACK_X: openstack_x.OpenstackXInstaller,
    },
    c.UNINSTALL: {
        c.NOVA: nova.NovaUninstaller,
        c.GLANCE: glance.GlanceUninstaller,
        c.QUANTUM: quantum.QuantumUninstaller,
        c.SWIFT: swift.SwiftUninstaller,
        c.HORIZON: horizon.HorizonUninstaller,
        c.KEYSTONE: keystone.KeystoneUninstaller,
        c.DB: db.DBUninstaller,
        c.RABBIT: rabbit.RabbitUninstaller,
        c.KEYSTONE_CLIENT: keystone_client.KeyStoneClientUninstaller,
        c.NOVA_CLIENT: nova_client.NovaClientUninstaller,
        c.OPENSTACK_X: openstack_x.OpenstackXUninstaller,
    },
    c.START: {
        c.NOVA: nova.NovaRuntime,
        c.GLANCE: glance.GlanceRuntime,
        c.QUANTUM: quantum.QuantumRuntime,
        c.SWIFT: swift.SwiftRuntime,
        c.HORIZON: horizon.HorizonRuntime,
        c.KEYSTONE: keystone.KeystoneRuntime,
        c.DB: db.DBRuntime,
        c.RABBIT: rabbit.RabbitRuntime,
        c.KEYSTONE_CLIENT: keystone_client.KeyStoneClientRuntime,
        c.NOVA_CLIENT: nova_client.NovaClientRuntime,
        c.OPENSTACK_X: openstack_x.OpenstackXRuntime,
    },
    c.STOP: {
        c.NOVA: nova.NovaRuntime,
        c.GLANCE: glance.GlanceRuntime,
        c.QUANTUM: quantum.QuantumRuntime,
        c.SWIFT: swift.SwiftRuntime,
        c.HORIZON: horizon.HorizonRuntime,
        c.KEYSTONE: keystone.KeystoneRuntime,
        c.DB: db.DBRuntime,
        c.RABBIT: rabbit.RabbitRuntime,
        c.KEYSTONE_CLIENT: keystone_client.KeyStoneClientRuntime,
        c.NOVA_CLIENT: nova_client.NovaClientRuntime,
        c.OPENSTACK_X: openstack_x.OpenstackXRuntime,
    },
}


def get_action_cls(action_name, component_name):
    action_cls_map = ACTION_CLASSES.get(action_name)
    if(not action_cls_map):
        return None
    cls = action_cls_map.get(component_name)
    return cls

