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

import operator
import os.path
import re

from devstack import log as logging

LOG = logging.getLogger("devstack.settings")

# These also have meaning outside python,
# ie in the pkg/pip listings so update there also!
UBUNTU11 = "ubuntu-oneiric"
RHEL6 = "rhel-6"

# What this program is called
PROG_NICE_NAME = "DEVSTACK"

# These 2 identify the json post and pre install sections
PRE_INSTALL = 'pre-install'
POST_INSTALL = 'post-install'

# Default interfaces for network ip detection
IPV4 = 'IPv4'
IPV6 = 'IPv6'
DEFAULT_NET_INTERFACE = 'eth0'
DEFAULT_NET_INTERFACE_IP_VERSION = IPV4

# Component name mappings
NOVA = "nova"
NOVA_CLIENT = 'nova-client'
GLANCE = "glance"
QUANTUM = "quantum"
SWIFT = "swift"
HORIZON = "horizon"
KEYSTONE = "keystone"
KEYSTONE_CLIENT = 'keystone-client'
DB = "db"
RABBIT = "rabbit"
OPENSTACK_X = 'openstack-x'
NOVNC = 'novnc'

# NCPU and NVOL are here as possible subcomponents of nova
# Thus they are not in the component name map or priority or dep list...
NCPU = "cpu"
NVOL = "vol"

COMPONENT_NAMES = [
    NOVA, NOVA_CLIENT,
    GLANCE,
    QUANTUM,
    SWIFT,
    HORIZON,
    KEYSTONE, KEYSTONE_CLIENT,
    OPENSTACK_X,
    DB,
    RABBIT,
    NOVNC,
]

# Ordering of install (lower priority means earlier)
COMPONENT_NAMES_PRIORITY = {
    DB: 1,
    RABBIT: 2,
    KEYSTONE: 3,
    GLANCE: 4,
    QUANTUM: 4,
    SWIFT: 4,
    NOVA_CLIENT: 4,
    NOVA: 5,
    KEYSTONE_CLIENT: 6,
    OPENSTACK_X: 6,
    NOVNC: 6,
    HORIZON: 10,
}

# When a component is asked for it may
# need another component, that dependency
# mapping is listed here
COMPONENT_DEPENDENCIES = {
    DB: [],
    KEYSTONE_CLIENT: [],
    RABBIT: [],
    GLANCE: [KEYSTONE, DB],
    KEYSTONE: [DB],
    NOVA: [KEYSTONE, GLANCE, DB, RABBIT, NOVA_CLIENT],
    SWIFT: [],
    NOVA_CLIENT: [],
    HORIZON: [KEYSTONE_CLIENT, GLANCE, NOVA_CLIENT, OPENSTACK_X],
    QUANTUM: [],
    NOVNC: [],
}

# Default subdirs of a components root directory
COMPONENT_TRACE_DIR = "traces"
COMPONENT_APP_DIR = "app"
COMPONENT_CONFIG_DIR = "config"

# This regex is used to extract a components options (if any) and its name
EXT_COMPONENT = re.compile(r"^\s*([\w-]+)(?:\((.*)\))?\s*$")

# Program
# actions
INSTALL = "install"
UNINSTALL = "uninstall"
START = "start"
STOP = "stop"
ACTIONS = [INSTALL, UNINSTALL, START, STOP]

# Where we should get the config file and where stacks config
# directory is
STACK_CONFIG_DIR = "conf"
STACK_PKG_DIR = os.path.join(STACK_CONFIG_DIR, "pkgs")
STACK_PIP_DIR = os.path.join(STACK_CONFIG_DIR, "pips")
STACK_CONFIG_LOCATION = os.path.join(STACK_CONFIG_DIR, "stack.ini")

# These regex is how we match python platform output to a known constant
KNOWN_DISTROS = {
    UBUNTU11: re.compile('Ubuntu(.*)oneiric', re.IGNORECASE),
    RHEL6: re.compile('redhat-6\.(\d+)', re.IGNORECASE),
}


# The pip files that each component needs
PIP_MAP = {
    NOVA:
        [],
    GLANCE:
        [],
    KEYSTONE:
        [
            os.path.join(STACK_PIP_DIR, 'keystone.json'),
        ],
    HORIZON:
        [
            os.path.join(STACK_PIP_DIR, 'horizon.json'),
        ],
    SWIFT:
        [],
    KEYSTONE_CLIENT:
        [],
    DB:
        [],
    RABBIT:
        [],
    QUANTUM:
        [],
}

# The pkg files that each component needs
PKG_MAP = {
    NOVA:
        [
            os.path.join(STACK_PKG_DIR, "general.json"),
            os.path.join(STACK_PKG_DIR, "nova.json"),
        ],
    QUANTUM:
        [],
    NOVA_CLIENT:
        [
            os.path.join(STACK_PKG_DIR, "general.json"),
            os.path.join(STACK_PKG_DIR, "nova-client.json"),
        ],
    GLANCE:
        [
            os.path.join(STACK_PKG_DIR, "general.json"),
            os.path.join(STACK_PKG_DIR, 'glance.json'),
        ],
    KEYSTONE:
        [
            os.path.join(STACK_PKG_DIR, "general.json"),
            os.path.join(STACK_PKG_DIR, 'keystone.json'),
        ],
    HORIZON:
        [
            os.path.join(STACK_PKG_DIR, "general.json"),
            os.path.join(STACK_PKG_DIR, 'horizon.json'),
        ],
    SWIFT:
        [
            os.path.join(STACK_PKG_DIR, "general.json"),
            os.path.join(STACK_PKG_DIR, 'swift.json'),
        ],
    KEYSTONE_CLIENT:
        [
            os.path.join(STACK_PKG_DIR, "keystone-client.json"),
        ],
    DB:
        [
            os.path.join(STACK_PKG_DIR, 'db.json'),
        ],
    RABBIT:
        [
            os.path.join(STACK_PKG_DIR, 'rabbitmq.json'),
        ],
    OPENSTACK_X:
        [
            os.path.join(STACK_PKG_DIR, 'openstackx.json'),
        ],
    NOVNC:
        [
            os.path.join(STACK_PKG_DIR, 'n-vnc.json'),
        ],
    NCPU:
        [
            os.path.join(STACK_PKG_DIR, 'n-cpu.json'),
        ],
    NVOL:
        [
            os.path.join(STACK_PKG_DIR, 'n-vol.json'),
        ],

}


def get_dependencies(component):
    return sorted(COMPONENT_DEPENDENCIES.get(component, list()))


def resolve_dependencies(components):
    active_components = list(components)
    new_components = set()
    while active_components:
        curr_comp = active_components.pop()
        component_deps = get_dependencies(curr_comp)
        new_components.add(curr_comp)
        for c in component_deps:
            if c in new_components or c in active_components:
                pass
            else:
                active_components.append(c)
    return new_components


def prioritize_components(components):
    #get the right component order (by priority)
    mporder = dict()
    for c in components:
        priority = COMPONENT_NAMES_PRIORITY.get(c)
        if priority is None:
            priority = sys.maxint
        mporder[c] = priority
    #sort by priority value
    priority_order = sorted(mporder.iteritems(), key=operator.itemgetter(1))
    #extract the final list ordering
    component_order = [x[0] for x in priority_order]
    return component_order


def parse_components(components, assume_all=False):
    #none provided, init it
    if not components:
        components = list()
    adjusted_components = dict()
    for c in components:
        mtch = EXT_COMPONENT.match(c)
        if mtch:
            component_name = mtch.group(1).lower().strip()
            if component_name not in COMPONENT_NAMES:
                LOG.warn("Unknown component named %s" % (component_name))
            else:
                component_opts = mtch.group(2)
                components_opts_cleaned = list()
                if not component_opts:
                    pass
                else:
                    sp_component_opts = component_opts.split(",")
                    for co in sp_component_opts:
                        cleaned_opt = co.strip()
                        if len(cleaned_opt):
                            components_opts_cleaned.append(cleaned_opt)
                adjusted_components[component_name] = components_opts_cleaned
        else:
            LOG.warn("Unparseable component %s" % (c))
    #should we adjust them to be all the components?
    if not adjusted_components and assume_all:
        all_components = dict()
        for c in COMPONENT_NAMES:
            all_components[c] = list()
        adjusted_components = all_components
    return adjusted_components
