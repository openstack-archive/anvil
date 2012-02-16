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
from devstack import exceptions as excp
from devstack import settings
from devstack import shell as sh

from devstack.components import db
from devstack.components import glance
from devstack.components import horizon
from devstack.components import keystone
from devstack.components import keystone_client
from devstack.components import melange
from devstack.components import melange_client
from devstack.components import nova
from devstack.components import nova_client
from devstack.components import novnc
from devstack.components import quantum
from devstack.components import quantum_client
from devstack.components import rabbit
from devstack.components import swift
from devstack.components import swift_keystone

# This determines what classes to use to install/uninstall/...
ACTION_CLASSES = {
    settings.INSTALL: {
        settings.DB: db.DBInstaller,
        settings.GLANCE: glance.GlanceInstaller,
        settings.HORIZON: horizon.HorizonInstaller,
        settings.KEYSTONE: keystone.KeystoneInstaller,
        settings.KEYSTONE_CLIENT: keystone_client.KeyStoneClientInstaller,
        settings.MELANGE: melange.MelangeInstaller,
        settings.MELANGE_CLIENT: melange_client.MelangeClientInstaller,
        settings.NOVA: nova.NovaInstaller,
        settings.NOVA_CLIENT: nova_client.NovaClientInstaller,
        settings.NOVNC: novnc.NoVNCInstaller,
        settings.QUANTUM: quantum.QuantumInstaller,
        settings.QUANTUM_CLIENT: quantum_client.QuantumClientInstaller,
        settings.RABBIT: rabbit.RabbitInstaller,
        settings.SWIFT: swift.SwiftInstaller,
        settings.SWIFT_KEYSTONE: swift_keystone.SwiftKeystoneInstaller,
    },
    settings.UNINSTALL: {
        settings.DB: db.DBUninstaller,
        settings.GLANCE: glance.GlanceUninstaller,
        settings.HORIZON: horizon.HorizonUninstaller,
        settings.KEYSTONE: keystone.KeystoneUninstaller,
        settings.KEYSTONE_CLIENT: keystone_client.KeyStoneClientUninstaller,
        settings.MELANGE: melange.MelangeUninstaller,
        settings.MELANGE_CLIENT: melange_client.MelangeClientUninstaller,
        settings.NOVA: nova.NovaUninstaller,
        settings.NOVA_CLIENT: nova_client.NovaClientUninstaller,
        settings.NOVNC: novnc.NoVNCUninstaller,
        settings.QUANTUM: quantum.QuantumUninstaller,
        settings.QUANTUM_CLIENT: quantum_client.QuantumClientUninstaller,
        settings.RABBIT: rabbit.RabbitUninstaller,
        settings.SWIFT: swift.SwiftUninstaller,
        settings.SWIFT_KEYSTONE: swift_keystone.SwiftKeystoneUninstaller,
    },
    settings.START: {
        settings.DB: db.DBRuntime,
        settings.GLANCE: glance.GlanceRuntime,
        settings.HORIZON: horizon.HorizonRuntime,
        settings.KEYSTONE: keystone.KeystoneRuntime,
        settings.KEYSTONE_CLIENT: keystone_client.KeyStoneClientRuntime,
        settings.MELANGE: melange.MelangeRuntime,
        settings.MELANGE_CLIENT: melange_client.MelangeClientRuntime,
        settings.NOVA: nova.NovaRuntime,
        settings.NOVA_CLIENT: nova_client.NovaClientRuntime,
        settings.NOVNC: novnc.NoVNCRuntime,
        settings.QUANTUM: quantum.QuantumRuntime,
        settings.QUANTUM_CLIENT: quantum_client.QuantumClientRuntime,
        settings.RABBIT: rabbit.RabbitRuntime,
        settings.SWIFT: swift.SwiftRuntime,
        settings.SWIFT_KEYSTONE: swift_keystone.SwiftKeystoneRuntime,
    },
}

ACTION_CLASSES[settings.STOP] = ACTION_CLASSES[settings.START]

_FAKE_ROOT_DIR = tempfile.gettempdir()


def get_default_components(distro):
    #this seems to be the default list of what to install by default
    #ENABLED_SERVICES=${ENABLED_SERVICES:-g-api,g-reg,key,n-api,
    #n-crt,n-obj,n-cpu,n-net,n-sch,n-novnc,n-xvnc,n-cauth,horizon,mysql,rabbit}
    def_components = dict()
    def_components[settings.GLANCE] = [
                                         glance.GAPI,
                                         glance.GREG,
                                      ]
    def_components[settings.KEYSTONE] = []
    def_components[settings.NOVA] = [
                                     nova.NAPI,
                                     nova.NCAUTH,
                                     nova.NCERT,
                                     nova.NCPU,
                                     nova.NNET,
                                     nova.NOBJ,
                                     nova.NSCHED,
                                     nova.NXVNC,
                                    ]
    def_components[settings.NOVNC] = []
    def_components[settings.HORIZON] = []
    def_components[settings.DB] = []
    def_components[settings.RABBIT] = []
    return def_components


def format_secs_taken(secs):
    output = "%.03f seconds" % (secs)
    output += " or %.02f minutes" % (secs / 60.0)
    return output


def get_action_cls(action_name, component_name, distro):
    action_cls_map = ACTION_CLASSES.get(action_name)
    if not action_cls_map:
        raise excp.StackException("Action %s has no component to class mapping" % (action_name))
    cls = action_cls_map.get(component_name)
    if not cls:
        raise excp.StackException("Action %s has no class entry for component %s" % (action_name, component_name))
    return cls


def get_config():
    cfg_fn = sh.canon_path(settings.STACK_CONFIG_LOCATION)
    config_instance = cfg.StackConfigParser()
    config_instance.read(cfg_fn)
    return config_instance


def get_components_deps(action_name, base_components, distro, root_dir):
    all_components = dict()
    active_names = list(base_components)
    if not root_dir:
        root_dir = _FAKE_ROOT_DIR
    while len(active_names):
        component = active_names.pop()
        component_opts = base_components.get(component) or list()
        cls = get_action_cls(action_name, component, distro)
        instance = cls(root=root_dir, opts=component_opts,
                        config=get_config())
        deps = instance.get_dependencies()
        if deps is None:
            deps = set()
        all_components[component] = set(deps)
        for d in deps:
            if d not in all_components and d not in active_names:
                active_names.append(d)
    return all_components
