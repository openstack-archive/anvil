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

from time import (localtime, strftime)
from termcolor import colored
import os
import platform
import re
import sys
import json
import netifaces
import operator

import Exceptions
import Logger
import Shell

#constant goodies
VERSION = 0x2
VERSION_STR = "%0.2f" % (VERSION)
DEVSTACK = 'DEVSTACK'

#these also have meaning outside python
#ie in the pkg/pip listings so update there also!
UBUNTU11 = "ubuntu-oneiric"
RHEL6 = "rhel-6"

#GIT master
MASTER_BRANCH = "master"

#other constants
PRE_INSTALL = 'pre-install'
POST_INSTALL = 'post-install'
IPV4 = 'IPv4'
IPV6 = 'IPv6'
DEFAULT_NET_INTERFACE = 'eth0'
DEFAULT_NET_INTERFACE_IP_VERSION = IPV4

#this regex is used for parameter substitution
PARAM_SUB_REGEX = re.compile(r"%([\w\d]+?)%")

#component name mappings
NOVA = "nova"
GLANCE = "glance"
QUANTUM = "quantum"
SWIFT = "swift"
HORIZON = "horizon"
KEYSTONE = "keystone"
KEYSTONE_CLIENT = 'keystone-client'
DB = "db"
RABBIT = "rabbit"
COMPONENT_NAMES = [NOVA, GLANCE, QUANTUM,
         SWIFT, HORIZON, KEYSTONE,
         DB, RABBIT, KEYSTONE_CLIENT]

#ordering of install (lower priority means earlier)
NAMES_PRIORITY = {
    DB: 1,
    RABBIT: 1,
    KEYSTONE: 2,
    GLANCE: 3,
    QUANTUM: 3,
    NOVA: 3,
    SWIFT: 3,
    HORIZON: 3,
    KEYSTONE_CLIENT: 4,
}

#when a component is asked for it may
#need another component, that dependency
#map is listed here...
COMPONENT_DEPENDENCIES = {
    DB: [],
    KEYSTONE_CLIENT: [],
    RABBIT: [],
    GLANCE: [KEYSTONE, DB],
    KEYSTONE: [DB],
    NOVA: [KEYSTONE, GLANCE, DB, RABBIT],
    SWIFT: [],
    HORIZON: [KEYSTONE_CLIENT, GLANCE],
    QUANTUM: [],
}

#program
#actions
INSTALL = "install"
UNINSTALL = "uninstall"
START = "start"
STOP = "stop"
ACTIONS = [INSTALL, UNINSTALL, START, STOP]

#these actions need to have there components dependencies
#to occur first (ie keystone starts before glance...)
DEP_ACTIONS_NEEDED = [START, STOP, INSTALL]

#this is used to map an action to a useful string for
#the welcome display...
WELCOME_MAP = {
    INSTALL: "Installer",
    UNINSTALL: "Uninstaller",
    START: "Runner",
    STOP: "Stopper",
}

#where we should get the config file...
STACK_CONFIG_DIR = "conf"
STACK_CFG_LOC = Shell.joinpths(STACK_CONFIG_DIR, "stack.ini")

#default subdirs of a components dir (valid unless overriden)
TRACE_DIR = "traces"
APP_DIR = "app"
CONFIG_DIR = "config"

#this regex is how we match python platform output to
#a known constant
KNOWN_OS = {
    UBUNTU11: re.compile('Ubuntu(.*)oneiric', re.IGNORECASE),
    RHEL6: re.compile('redhat-6\.(\d+)', re.IGNORECASE),
}

#the pip files that each component
#needs
PIP_MAP = {
    NOVA:
        [],
    GLANCE:
        [],
    KEYSTONE:
        [
            Shell.joinpths(STACK_CONFIG_DIR, "pips", 'keystone.json'),
        ],
    HORIZON:
        [
            Shell.joinpths(STACK_CONFIG_DIR, "pips", 'horizon.json'),
        ],
    SWIFT:
        [],
    KEYSTONE_CLIENT:
        [],
    DB:
        [],
    RABBIT:
        [],
}

#the pkg files that each component
#needs
PKG_MAP = {
    NOVA:
        [
            Shell.joinpths(STACK_CONFIG_DIR, "pkgs", "nova.json"),
            Shell.joinpths(STACK_CONFIG_DIR, "pkgs", "general.json"),
        ],
    GLANCE:
        [
            Shell.joinpths(STACK_CONFIG_DIR, "pkgs", "general.json"),
            Shell.joinpths(STACK_CONFIG_DIR, "pkgs", 'glance.json'),
        ],
    KEYSTONE:
        [
            Shell.joinpths(STACK_CONFIG_DIR, "pkgs", "general.json"),
            Shell.joinpths(STACK_CONFIG_DIR, "pkgs", 'keystone.json'),
        ],
    HORIZON:
        [
            Shell.joinpths(STACK_CONFIG_DIR, "pkgs", "general.json"),
            Shell.joinpths(STACK_CONFIG_DIR, "pkgs", 'horizon.json'),
        ],
    SWIFT:
        [
            Shell.joinpths(STACK_CONFIG_DIR, "pkgs", "general.json"),
            Shell.joinpths(STACK_CONFIG_DIR, "pkgs", 'swift.json'),
        ],
    KEYSTONE_CLIENT:
        [
            Shell.joinpths(STACK_CONFIG_DIR, "pkgs", "keystone-client.json"),
        ],
    DB:
        [
            Shell.joinpths(STACK_CONFIG_DIR, "pkgs", 'db.json'),
        ],
    RABBIT:
        [
            Shell.joinpths(STACK_CONFIG_DIR, "pkgs", 'rabbitmq.json'),
        ],
}

LOG = Logger.getLogger("install.util")


def resolve_dependencies(action, components):
    if(action in DEP_ACTIONS_NEEDED):
        new_components = list()
        for c in components:
            component_deps = list(set(fetch_deps(c)))
            if(len(component_deps)):
                new_components = new_components + component_deps
            new_components.append(c)
        return set(new_components)
    else:
        return set(components)


def execute_template(*cmds, **kargs):
    if(not cmds or len(cmds) == 0):
        return
    params_replacements = kargs.pop('params')
    ignore_missing = kargs.pop('ignore_missing', False)
    for cmdinfo in cmds:
        cmd_to_run_templ = cmdinfo.get("cmd")
        cmd_to_run = list()
        for piece in cmd_to_run_templ:
            if(params_replacements and len(params_replacements)):
                cmd_to_run.append(param_replace(piece, params_replacements,
                    ignore_missing=ignore_missing))
            else:
                cmd_to_run.append(piece)
        stdin_templ = cmdinfo.get('stdin')
        stdin = None
        if(stdin_templ and len(stdin_templ)):
            stdin_full = list()
            for piece in stdin_templ:
                if(params_replacements and len(params_replacements)):
                    stdin_full.append(param_replace(piece, params_replacements,
                        ignore_missing=ignore_missing))
                else:
                    stdin_full.append(piece)
            stdin = joinlinesep(*stdin_full)
        root_run = cmdinfo.get('run_as_root', False)
        Shell.execute(*cmd_to_run, run_as_root=root_run, process_input=stdin, **kargs)


def fetch_deps(component, add=False):
    if(add):
        deps = list([component])
    else:
        deps = list()
    cdeps = COMPONENT_DEPENDENCIES.get(component)
    if(cdeps and len(cdeps)):
        for d in cdeps:
            deps = deps + fetch_deps(d, True)
    return deps


def prioritize_components(components):
    #get the right component order (by priority)
    mporder = dict()
    for c in components:
        priority = NAMES_PRIORITY.get(c)
        if(priority == None):
            priority = sys.maxint
        mporder[c] = priority
    #sort by priority value
    priority_order = sorted(mporder.iteritems(), key=operator.itemgetter(1))
    #extract the right order
    component_order = [x[0] for x in priority_order]
    return component_order


def component_paths(root, component_name):
    component_root = Shell.joinpths(root, component_name)
    tracedir = Shell.joinpths(component_root, TRACE_DIR)
    appdir = Shell.joinpths(component_root, APP_DIR)
    cfgdir = Shell.joinpths(component_root, CONFIG_DIR)
    return (component_root, tracedir, appdir, cfgdir)


def load_json(fn):
    data = Shell.load_file(fn)
    lines = data.splitlines()
    new_lines = list()
    for line in lines:
        if(line.lstrip().startswith('#')):
            continue
        new_lines.append(line)
    data = joinlinesep(*new_lines)
    return json.loads(data)


def get_host_ip(cfg=None):
    ip = None
    if(cfg):
        cfg_ip = cfg.get('default', 'host_ip')
        if(cfg_ip and len(cfg_ip)):
            ip = cfg_ip
    if(ip == None):
        interfaces = get_interfaces()
        def_info = interfaces.get(DEFAULT_NET_INTERFACE)
        if(def_info):
            ipinfo = def_info.get(DEFAULT_NET_INTERFACE_IP_VERSION)
            if(ipinfo):
                ip = ipinfo.get('addr')
    if(ip == None):
        msg = "Your host does not have an ip address!"
        raise Exceptions.NoIpException(msg)
    LOG.debug("Determined host ip to be: \"%s\"" % (ip))
    return ip


def get_interfaces():
    interfaces = dict()
    for intfc in netifaces.interfaces():
        interface_info = dict()
        interface_addresses = netifaces.ifaddresses(intfc)
        ip6 = interface_addresses.get(netifaces.AF_INET6)
        if(ip6 and len(ip6)):
            #just take the first
            interface_info[IPV6] = ip6[0]
        ip4 = interface_addresses.get(netifaces.AF_INET)
        if(ip4 and len(ip4)):
            #just take the first
            interface_info[IPV4] = ip4[0]
        #there are others but this is good for now
        interfaces[intfc] = interface_info
    return interfaces


def determine_os():
    found_os = None
    plt = platform.platform()
    for (known_os, pattern) in KNOWN_OS.items():
        if(pattern.search(plt)):
            found_os = known_os
            break
    return (found_os, plt)


def get_pip_list(distro, component):
    LOG.info("Getting pip packages for distro %s and component %s." % (distro, component))
    all_pkgs = dict()
    fns = PIP_MAP.get(component)
    if(fns == None):
        return all_pkgs
    #load + merge them
    for fn in fns:
        js = load_json(fn)
        distro_pkgs = js.get(distro)
        if(distro_pkgs and len(distro_pkgs)):
            combined = dict(all_pkgs)
            for (pkgname, pkginfo) in distro_pkgs.items():
                #we currently just overwrite
                combined[pkgname] = pkginfo
            all_pkgs = combined
    return all_pkgs


def get_pkg_list(distro, component):
    LOG.info("Getting packages for distro %s and component %s." % (distro, component))
    all_pkgs = dict()
    fns = PKG_MAP.get(component)
    if(fns == None):
        return all_pkgs
    #load + merge them
    for fn in fns:
        js = load_json(fn)
        distro_pkgs = js.get(distro)
        if(distro_pkgs and len(distro_pkgs)):
            combined = dict(all_pkgs)
            for (pkgname, pkginfo) in distro_pkgs.items():
                if(pkgname in all_pkgs.keys()):
                    oldpkginfo = all_pkgs.get(pkgname) or dict()
                    newpkginfo = dict(oldpkginfo)
                    for (infokey, infovalue) in pkginfo.items():
                        #this is expected to be a list of cmd actions
                        #so merge that accordingly
                        if(infokey == PRE_INSTALL or infokey == POST_INSTALL):
                            oldinstalllist = oldpkginfo.get(infokey) or []
                            infovalue = oldinstalllist + infovalue
                        newpkginfo[infokey] = infovalue
                    combined[pkgname] = newpkginfo
                else:
                    combined[pkgname] = pkginfo
            all_pkgs = combined
    return all_pkgs


def joinlinesep(*pieces):
    return os.linesep.join(pieces)


def param_replace(text, replacements, ignore_missing=False):

    if(not replacements or len(replacements) == 0):
        return text

    if(len(text) == 0):
        return text

    if(ignore_missing):
        LOG.debug("Performing parameter replacements (ignoring missing) on %s" % (text))
    else:
        LOG.debug("Performing parameter replacements (not ignoring missing) on %s" % (text))

    def replacer(match):
        org = match.group(0)
        name = match.group(1)
        v = replacements.get(name)
        if(v == None and ignore_missing):
            v = org
        elif(v == None and not ignore_missing):
            msg = "No replacement found for parameter %s" % (org)
            raise Exceptions.NoReplacementException(msg)
        else:
            LOG.debug("Replacing [%s] with [%s]" % (org, str(v)))
        return str(v)

    return PARAM_SUB_REGEX.sub(replacer, text)


def welcome(program_action):
    formatted_action = WELCOME_MAP.get(program_action)
    lower = "!%s v%s!" % (formatted_action.upper(), VERSION)
    welcome = r'''
  ___  ____  _____ _   _ ____ _____  _    ____ _  __
 / _ \|  _ \| ____| \ | / ___|_   _|/ \  / ___| |/ /
| | | | |_) |  _| |  \| \___ \ | | / _ \| |   | ' /
| |_| |  __/| |___| |\  |___) || |/ ___ \ |___| . \
 \___/|_|   |_____|_| \_|____/ |_/_/   \_\____|_|\_\

'''
    welcome = "  " + welcome.strip()
    lower_out = (" " * 17) + colored(DEVSTACK, 'green') + ": " + colored(lower, 'blue')
    msg = welcome + os.linesep + lower_out
    print(msg)


def rcf8222date():
    return strftime("%a, %d %b %Y %H:%M:%S", localtime())


def fs_safe_date():
    return strftime("%m_%d_%G-%H-%M-%S", localtime())
