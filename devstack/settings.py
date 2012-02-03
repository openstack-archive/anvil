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
import re

# These also have meaning outside python,
# ie in the pkg/pip listings so update there also!
UBUNTU11 = "ubuntu-oneiric"
RHEL6 = "rhel-6"

# What this program is called
PROG_NICE_NAME = "DEVSTACKpy"

# These 2 identify the json post and pre install sections
PRE_INSTALL = 'pre-install'
POST_INSTALL = 'post-install'

# Ip version constants for network ip detection
IPV4 = 'IPv4'
IPV6 = 'IPv6'

# Component name mappings
NOVA = "nova"
NOVA_CLIENT = 'nova-client'
GLANCE = "glance"
QUANTUM = "quantum"
QUANTUM_CLIENT = 'quantum-client'
SWIFT = "swift"
SWIFT_KEYSTONE = "swift_keystone"
HORIZON = "horizon"
KEYSTONE = "keystone"
KEYSTONE_CLIENT = 'keystone-client'
DB = "db"
RABBIT = "rabbit"
NOVNC = 'novnc'
XVNC = 'xvnc'
COMPONENT_NAMES = [
    NOVA, NOVA_CLIENT,
    GLANCE,
    QUANTUM, QUANTUM_CLIENT,
    SWIFT, SWIFT_KEYSTONE,
    HORIZON,
    KEYSTONE, KEYSTONE_CLIENT,
    DB,
    RABBIT,
    NOVNC,
]

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
    SWIFT_KEYSTONE: [SWIFT],
    NOVA_CLIENT: [],
    HORIZON: [KEYSTONE_CLIENT, GLANCE, NOVA_CLIENT],
    #the db isn't always a dependency (depending on the quantum component to be activated)
    #for now assume it is (TODO make it better?)
    #the client isn't always needed either (TODO make it better?)
    QUANTUM: [DB, QUANTUM_CLIENT],
    NOVNC: [NOVA],
    QUANTUM_CLIENT: [],
}

# Default subdirs of a components root directory
COMPONENT_TRACE_DIR = "traces"
COMPONENT_APP_DIR = "app"
COMPONENT_CONFIG_DIR = "config"

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
    UBUNTU11: re.compile(r'Ubuntu(.*)oneiric', re.IGNORECASE),
    RHEL6: re.compile(r'redhat-6\.2', re.IGNORECASE),
}
