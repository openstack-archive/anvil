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
import sys

# What this program is called
PROG_NICE_NAME = "DEVSTACKpy"

# Ip version constants for network ip detection
IPV4 = 'IPv4'
IPV6 = 'IPv6'

# Different run types supported
RUN_TYPE_FORK = "FORK"
RUN_TYPE_UPSTART = "UPSTART"
RUN_TYPE_SCREEN = "SCREEN"
RUN_TYPE_DEF = RUN_TYPE_FORK
RUN_TYPES_KNOWN = [RUN_TYPE_UPSTART,
                    RUN_TYPE_FORK,
                    RUN_TYPE_SCREEN,
                    RUN_TYPE_DEF]

# Used to find the type in trace files
RUN_TYPE_TYPE = "TYPE"

# Default subdirs of a components root directory
COMPONENT_TRACE_DIR = "traces"
COMPONENT_APP_DIR = "app"
COMPONENT_CONFIG_DIR = "config"

# RC files generated / used
RC_FN_TEMPL = "os-%s.rc"
OSRC_FN = RC_FN_TEMPL % ('core')

# Where the configs and templates should be at.
STACK_BIN_DIR = os.path.abspath(os.path.dirname(sys.argv[0]))
STACK_CONFIG_DIR = os.path.join(STACK_BIN_DIR, "conf")
STACK_DISTRO_DIR = os.path.join(STACK_CONFIG_DIR, "distros")
STACK_TEMPLATE_DIR = os.path.join(STACK_CONFIG_DIR, "templates")
STACK_CONFIG_LOCATION = os.path.join(STACK_CONFIG_DIR, "stack.ini")
