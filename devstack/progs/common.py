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

import tempfile

from devstack import cfg
from devstack import settings
from devstack import shell as sh

from devstack.components import db
from devstack.components import glance
from devstack.components import horizon
from devstack.components import keystone
from devstack.components import keystone_client
from devstack.components import nova
from devstack.components import nova_client
from devstack.components import novnc
from devstack.components import openstack_x
from devstack.components import quantum
from devstack.components import quantum_client
from devstack.components import rabbit
from devstack.components import swift

# This determines what classes to use to install/uninstall/...
ACTION_CLASSES = {
    settings.INSTALL: {
        settings.NOVA: nova.NovaInstaller,
        settings.GLANCE: glance.GlanceInstaller,
        settings.QUANTUM: quantum.QuantumInstaller,
        settings.SWIFT: swift.SwiftInstaller,
        settings.HORIZON: horizon.HorizonInstaller,
        settings.KEYSTONE: keystone.KeystoneInstaller,
        settings.DB: db.DBInstaller,
        settings.RABBIT: rabbit.RabbitInstaller,
        settings.KEYSTONE_CLIENT: keystone_client.KeyStoneClientInstaller,
        settings.NOVA_CLIENT: nova_client.NovaClientInstaller,
        settings.OPENSTACK_X: openstack_x.OpenstackXInstaller,
        settings.NOVNC: novnc.NoVNCInstaller,
        settings.QUANTUM_CLIENT: quantum_client.QuantumClientInstaller,
    },
    settings.UNINSTALL: {
        settings.NOVA: nova.NovaUninstaller,
        settings.GLANCE: glance.GlanceUninstaller,
        settings.QUANTUM: quantum.QuantumUninstaller,
        settings.SWIFT: swift.SwiftUninstaller,
        settings.HORIZON: horizon.HorizonUninstaller,
        settings.KEYSTONE: keystone.KeystoneUninstaller,
        settings.DB: db.DBUninstaller,
        settings.RABBIT: rabbit.RabbitUninstaller,
        settings.KEYSTONE_CLIENT: keystone_client.KeyStoneClientUninstaller,
        settings.NOVA_CLIENT: nova_client.NovaClientUninstaller,
        settings.OPENSTACK_X: openstack_x.OpenstackXUninstaller,
        settings.NOVNC: novnc.NoVNCUninstaller,
        settings.QUANTUM_CLIENT: quantum_client.QuantumClientUninstaller,
    },
    settings.START: {
        settings.NOVA: nova.NovaRuntime,
        settings.GLANCE: glance.GlanceRuntime,
        settings.QUANTUM: quantum.QuantumRuntime,
        settings.SWIFT: swift.SwiftRuntime,
        settings.HORIZON: horizon.HorizonRuntime,
        settings.KEYSTONE: keystone.KeystoneRuntime,
        settings.DB: db.DBRuntime,
        settings.RABBIT: rabbit.RabbitRuntime,
        settings.KEYSTONE_CLIENT: keystone_client.KeyStoneClientRuntime,
        settings.NOVA_CLIENT: nova_client.NovaClientRuntime,
        settings.OPENSTACK_X: openstack_x.OpenstackXRuntime,
        settings.NOVNC: novnc.NoVNCRuntime,
        settings.QUANTUM_CLIENT: quantum_client.QuantumClientRuntime,
    },
    settings.STOP: {
        settings.NOVA: nova.NovaRuntime,
        settings.GLANCE: glance.GlanceRuntime,
        settings.QUANTUM: quantum.QuantumRuntime,
        settings.SWIFT: swift.SwiftRuntime,
        settings.HORIZON: horizon.HorizonRuntime,
        settings.KEYSTONE: keystone.KeystoneRuntime,
        settings.DB: db.DBRuntime,
        settings.RABBIT: rabbit.RabbitRuntime,
        settings.KEYSTONE_CLIENT: keystone_client.KeyStoneClientRuntime,
        settings.NOVA_CLIENT: nova_client.NovaClientRuntime,
        settings.OPENSTACK_X: openstack_x.OpenstackXRuntime,
        settings.NOVNC: novnc.NoVNCRuntime,
        settings.QUANTUM_CLIENT: quantum_client.QuantumClientRuntime,
    },
}

_FAKE_ROOT_DIR = tempfile.gettempdir()


def get_default_components():
    #this seems to be the default list of what to install by default
    #ENABLED_SERVICES=${ENABLED_SERVICES:-g-api,g-reg,key,n-api,
    #n-crt,n-obj,n-cpu,n-net,n-sch,n-novnc,n-xvnc,n-cauth,horizon,mysql,rabbit}
    def_components = dict()
    def_components[settings.GLANCE] = [
                                         glance.GAPI,
                                         glance.GREG,
                                      ]
    def_components[settings.KEYSTONE] = []
    #TODO add in xvnc?
    def_components[settings.NOVA] = [
                                     nova.NAPI,
                                     nova.NCAUTH,
                                     nova.NCERT,
                                     nova.NCPU,
                                     nova.NNET,
                                     nova.NOBJ,
                                     nova.NSCHED,
                                     nova.NVOL,
                                    ]
    def_components[settings.NOVNC] = []
    def_components[settings.HORIZON] = []
    def_components[settings.DB] = []
    def_components[settings.RABBIT] = []
    return def_components


def get_action_cls(action_name, component_name):
    action_cls_map = ACTION_CLASSES.get(action_name)
    return action_cls_map.get(component_name)


def get_config():
    cfg_fn = sh.canon_path(settings.STACK_CONFIG_LOCATION)
    config_instance = cfg.EnvConfigParser()
    config_instance.read(cfg_fn)
    return config_instance


def get_components_deps(action_name, base_components):
    all_components = dict()
    active_names = list(base_components)
    while len(active_names):
        component = active_names.pop()
        component_opts = base_components.get(component) or list()
        cls = get_action_cls(action_name, component)
        instance = cls(root=_FAKE_ROOT_DIR, opts=component_opts,
                        config=get_config())
        deps = instance.get_dependencies()
        if deps is None:
            deps = set()
        all_components[component] = set(deps)
        for d in deps:
            if d not in all_components and d not in active_names:
                active_names.append(d)
    return all_components
