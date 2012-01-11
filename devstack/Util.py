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

import Exceptions
from Exceptions import (BadRegexException,
                        NoReplacementException,
                        FileException)
import Logger
import Shell
from Shell import (joinpths, load_json)

from time import (localtime, strftime)
from termcolor import colored

import subprocess
import platform
import re
import os

#constant goodies
VERSION = 0x2

#these also have meaning outside python
#ie in the pkg listings so update there also!
UBUNTU12 = "ubuntu-oneiric"
RHEL6 = "rhel-6"

#GIT master
MASTER_BRANCH = "master"

#other constants
DB_DSN = '%s://%s:%s@%s/%s'

#component name mappings
NOVA = "nova"
GLANCE = "glance"
QUANTUM = "quantum"
SWIFT = "swift"
HORIZON = "horizon"
KEYSTONE = "keystone"
DB = "db"
RABBIT = "rabbit"

NAMES = [NOVA, GLANCE, QUANTUM,
         SWIFT, HORIZON, KEYSTONE,
         DB, RABBIT]

#ordering of install (lower priority means earlier)
NAMES_PRIORITY = {
    DB: 1,
    RABBIT: 1,
    KEYSTONE: 2,
    GLANCE: 3,
    QUANTUM: 4,
    NOVA: 5,
    SWIFT: 6,
    HORIZON: 7,
}

#when a component is asked for it may
#need another component, that dependency
#map is listed here...
COMPONENT_DEPENDENCIES = {
    DB: [],
    RABBIT: [],
    GLANCE: [KEYSTONE, DB],
    KEYSTONE: [DB],
    NOVA: [KEYSTONE, GLANCE, DB, RABBIT],
    SWIFT: [],
    HORIZON: [],
    QUANTUM: [],
}

#program
#actions
INSTALL = "install"
UNINSTALL = "uninstall"
START = "start"
STOP = "stop"

ACTIONS = [INSTALL, UNINSTALL, START, STOP]

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
CFG_LOC = joinpths(STACK_CONFIG_DIR, "stack.ini")

#this regex is how we match python platform output to
#a known constant
KNOWN_OS = {
    UBUNTU12: '/Ubuntu(.*)oneiric/i',
    RHEL6: '/redhat-6\.(\d+)/i',
}

#the pkg files that each component
#needs
PKG_MAP = {
    NOVA:
           [
             joinpths(STACK_CONFIG_DIR, "pkgs", "nova.pkg"),
             joinpths(STACK_CONFIG_DIR, "pkgs", "general.pkg"),
           ],
    GLANCE:
           [
             joinpths(STACK_CONFIG_DIR, "pkgs", "general.pkg"),
             joinpths(STACK_CONFIG_DIR, "pkgs", 'glance.pkg'),
           ],
    KEYSTONE:
           [
             joinpths(STACK_CONFIG_DIR, "pkgs", "general.pkg"),
             joinpths(STACK_CONFIG_DIR, "pkgs", 'keystone.pkg'),
           ],
    HORIZON:
           [
             joinpths(STACK_CONFIG_DIR, "pkgs", "general.pkg"),
             joinpths(STACK_CONFIG_DIR, "pkgs", 'horizon.pkg'),
           ],
    SWIFT:
           [
             joinpths(STACK_CONFIG_DIR, "pkgs", "general.pkg"),
             joinpths(STACK_CONFIG_DIR, "pkgs", 'swift.pkg'),
           ],
    DB:
           [
             joinpths(STACK_CONFIG_DIR, "pkgs", 'db.pkg'),
           ],
    RABBIT:
           [
             joinpths(STACK_CONFIG_DIR, "pkgs", 'rabbitmq.pkg'),
           ],
}

#subdirs of a components dir
TRACE_DIR = "traces"
APP_DIR = "app"
CONFIG_DIR = "config"

#our ability to create regexes
#which is more like php, which is nicer
#for modifiers...
REGEX_MATCHER = re.compile("^/(.*?)/([a-z]*)$")

LOG = Logger.getLogger("install.util")


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


def component_pths(root, compnent_type):
    component_root = joinpths(root, compnent_type)
    tracedir = joinpths(component_root, TRACE_DIR)
    appdir = joinpths(component_root, APP_DIR)
    cfgdir = joinpths(component_root, CONFIG_DIR)
    out = dict()
    out['root_dir'] = component_root
    out['trace_dir'] = tracedir
    out['app_dir'] = appdir
    out['config_dir'] = cfgdir
    return out


def get_interfaces():
    import netifaces
    interfaces = dict()
    for intfc in netifaces.interfaces():
        interfaces[intfc] = netifaces.ifaddresses(intfc)
    return interfaces


def create_regex(format):
    mtch = REGEX_MATCHER.match(format)
    if(not mtch):
        raise BadRegexException("Badly formatted pre-regex: " + format)
    else:
        toberegex = mtch.group(1)
        options = mtch.group(2).lower()
        flags = 0
        if(options.find("i") != -1):
            flags = flags | re.IGNORECASE
        if(options.find("m") != -1):
            flags = flags | re.MULTILINE
        if(options.find("u") != -1):
            flags = flags | re.UNICODE
        return re.compile(toberegex, flags)


def get_dbdsn(cfg, dbname):
    user = cfg.get("db", "sql_user")
    host = cfg.get("db", "sql_host")
    dbtype = cfg.get("db", "type")
    pw = cfg.getpw("passwords", "sql")
    return DB_DSN % (dbtype, user, pw, host, dbname)


def determine_os():
    os = None
    plt = platform.platform()
    for aos, pat in KNOWN_OS.items():
        reg = create_regex(pat)
        if(reg.search(plt)):
            os = aos
            break
    return (os, plt)


def get_pkg_list(distro, component):
    LOG.info("Getting packages for distro %s and component %s." % (distro, component))
    all_pkgs = dict()
    fns = PKG_MAP.get(component)
    if(fns == None):
        #guess none needed
        return all_pkgs
    #load + merge them
    for fn in fns:
        js = load_json(fn)
        if(type(js) is dict):
            distromp = js.get(distro)
            if(distromp != None and type(distromp) is dict):
                all_pkgs = dict(all_pkgs.items() + distromp.items())
    return all_pkgs


def joinlinesep(*pieces):
    return os.linesep.join(*pieces)

def param_replace(text, replacements):
    if(len(replacements) == 0 or len(text) == 0):
        return text

    def replacer(m):
        org = m.group()
        name = m.group(1)
        v = replacements.get(name)
        if(v == None):
            msg = "No replacement found for parameter %s" % (org)
            raise NoReplacementException(msg)
        return str(v)

    ntext = re.sub("%([\\w\\d]+?)%", replacer, text)
    return ntext


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
    lowerc = " " * 21 + colored(lower, 'blue')
    msg = welcome + "\n" + lowerc
    print(msg)


def rcf8222date():
    return strftime("%a, %d %b %Y %H:%M:%S", localtime())


def fsSafeDate():
    return strftime("%m_%d_%G-%H-%M-%S", localtime())
