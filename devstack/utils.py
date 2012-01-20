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

import json
import netifaces
import operator
import os
import platform
import re
import string
import sys

from termcolor import colored

from devstack import constants
from devstack import exceptions as excp
from devstack import log as logging
from devstack import shell as sh
from devstack import version

PARAM_SUB_REGEX = re.compile(r"%([\w\d]+?)%")
LOG = logging.getLogger("devstack.util")


def get_dependencies(component):
    deps = constants.COMPONENT_DEPENDENCIES.get(component, list())
    return sorted(deps)


def resolve_dependencies(components):
    new_components = list()
    for c in components:
        component_deps = list(set(fetch_dependencies(c)))
        if(len(component_deps)):
            new_components = new_components + component_deps
        new_components.append(c)
    return set(new_components)


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
        sh.execute(*cmd_to_run, run_as_root=root_run, process_input=stdin, **kargs)


def fetch_dependencies(component, add=False):
    if(add):
        deps = list([component])
    else:
        deps = list()
    cdeps = get_dependencies(component)
    if(cdeps and len(cdeps)):
        for d in cdeps:
            deps = deps + fetch_dependencies(d, True)
    return deps


def prioritize_components(components):
    #get the right component order (by priority)
    mporder = dict()
    priorities = constants.COMPONENT_NAMES_PRIORITY
    for c in components:
        priority = priorities.get(c)
        if(priority == None):
            priority = sys.maxint
        mporder[c] = priority
    #sort by priority value
    priority_order = sorted(mporder.iteritems(), key=operator.itemgetter(1))
    #extract the right order
    component_order = [x[0] for x in priority_order]
    return component_order


def component_paths(root, component_name):
    component_root = sh.joinpths(root, component_name)
    tracedir = sh.joinpths(component_root, constants.COMPONENT_TRACE_DIR)
    appdir = sh.joinpths(component_root, constants.COMPONENT_APP_DIR)
    cfgdir = sh.joinpths(component_root, constants.COMPONENT_CONFIG_DIR)
    return (component_root, tracedir, appdir, cfgdir)


def load_json(fn):
    data = sh.load_file(fn)
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
        def_info = interfaces.get(constants.DEFAULT_NET_INTERFACE)
        if(def_info):
            ipinfo = def_info.get(constants.DEFAULT_NET_INTERFACE_IP_VERSION)
            if(ipinfo):
                ip = ipinfo.get('addr')
    if(ip == None):
        msg = "Your host does not have an ip address!"
        raise excp.NoIpException(msg)
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
            interface_info[constants.IPV6] = ip6[0]
        ip4 = interface_addresses.get(netifaces.AF_INET)
        if(ip4 and len(ip4)):
            #just take the first
            interface_info[constants.IPV4] = ip4[0]
        #there are others but this is good for now
        interfaces[intfc] = interface_info
    return interfaces


def determine_distro():
    plt = platform.platform()
    #ensure its a linux distro
    (distname, version, id) = platform.linux_distribution()
    if(not distname):
        return (None, plt)
    #attempt to match it to our platforms
    found_os = None
    for (known_os, pattern) in constants.KNOWN_DISTROS.items():
        if(pattern.search(plt)):
            found_os = known_os
            break
    return (found_os, plt)


def get_pip_list(distro, component):
    LOG.info("Getting pip packages for distro %s and component %s." % (distro, component))
    all_pkgs = dict()
    fns = constants.PIP_MAP.get(component)
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
    fns = constants.PKG_MAP.get(component)
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
                        if(infokey == constants.PRE_INSTALL or infokey == constants.POST_INSTALL):
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
            raise excp.NoReplacementException(msg)
        else:
            LOG.debug("Replacing [%s] with [%s]" % (org, str(v)))
        return str(v)

    return PARAM_SUB_REGEX.sub(replacer, text)


def welcome(program_action):
    formatted_action = constants.WELCOME_MAP.get(program_action, "")
    ver_str = version.version_string()
    lower = "!%s %s!" % (formatted_action.upper(), ver_str)
    welcome = r'''
  ___  ____  _____ _   _ ____ _____  _    ____ _  __
 / _ \|  _ \| ____| \ | / ___|_   _|/ \  / ___| |/ /
| | | | |_) |  _| |  \| \___ \ | | / _ \| |   | ' /
| |_| |  __/| |___| |\  |___) || |/ ___ \ |___| . \
 \___/|_|   |_____|_| \_|____/ |_/_/   \_\____|_|\_\

'''
    #this seems needed, weird...
    welcome = "  " + welcome.strip()
    max_len = 0
    for line in welcome.splitlines():
        if(len(line) > max_len):
            max_len = len(line)
    lower_out = colored(constants.PROG_NICE_NAME, 'green') + \
        ": " + colored(lower, 'blue')
    center_len = (max_len + max_len / 3)
    lower_out = string.center(lower_out, center_len)
    msg = welcome + os.linesep + lower_out
    print(msg)
