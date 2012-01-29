# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#
#    Copyright 2011 OpenStack LLC.
#    All Rights Reserved.
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
import os
import platform
import random
import re
import traceback

#requires http://pypi.python.org/pypi/termcolor
#but the colors make it worth it :-)
from termcolor import colored

from devstack import exceptions as excp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import version


PARAM_SUB_REGEX = re.compile(r"%([\w\d]+?)%")
EXT_COMPONENT = re.compile(r"^\s*([\w-]+)(?:\((.*)\))?\s*$")
LOG = logging.getLogger("devstack.util")
TEMPLATE_EXT = ".tpl"


def load_template(component, fn):
    actual_fn = fn + TEMPLATE_EXT
    full_pth = os.path.join(settings.STACK_CONFIG_DIR, component, actual_fn)
    contents = sh.load_file(full_pth)
    return (full_pth, contents)


def execute_template(*cmds, **kargs):
    params_replacements = kargs.pop('params', None)
    tracewriter = kargs.pop('tracewriter', None)
    ignore_missing = kargs.pop('ignore_missing', False)
    cmd_results = list()
    for cmdinfo in cmds:
        cmd_to_run_templ = cmdinfo.get("cmd")
        cmd_to_run = list()
        for piece in cmd_to_run_templ:
            if params_replacements and len(params_replacements):
                cmd_to_run.append(param_replace(piece, params_replacements,
                    ignore_missing=ignore_missing))
            else:
                cmd_to_run.append(piece)
        stdin_templ = cmdinfo.get('stdin')
        stdin = None
        if stdin_templ and len(stdin_templ):
            stdin_full = list()
            for piece in stdin_templ:
                if params_replacements and len(params_replacements):
                    stdin_full.append(param_replace(piece, params_replacements,
                        ignore_missing=ignore_missing))
                else:
                    stdin_full.append(piece)
            stdin = joinlinesep(*stdin_full)
        root_run = cmdinfo.get('run_as_root', False)
        exec_res = sh.execute(*cmd_to_run, run_as_root=root_run, process_input=stdin, **kargs)
        if tracewriter:
            tracewriter.exec_cmd(cmd_to_run, exec_res)
        cmd_results.append(exec_res)
    return cmd_results


def to_bytes(text):
    byte_val = 0
    if not text:
        return byte_val
    if text[-1].upper() == 'G':
        byte_val = int(text[:-1]) * 1024 ** 3
    elif text[-1].upper() == 'M':
        byte_val = int(text[:-1]) * 1024 ** 2
    elif text[-1].upper() == 'K':
        byte_val = int(text[:-1]) * 1024
    elif text[-1].upper() == 'B':
        byte_val = int(text[:-1])
    else:
        byte_val = int(text)
    return byte_val


def load_json(fn):
    data = sh.load_file(fn)
    lines = data.splitlines()
    new_lines = list()
    for line in lines:
        if line.lstrip().startswith('#'):
            continue
        new_lines.append(line)
    data = joinlinesep(*new_lines)
    return json.loads(data)


def get_host_ip(def_net_ifc, def_ip_version):
    ip = None
    interfaces = get_interfaces()
    def_info = interfaces.get(def_net_ifc)
    if def_info:
        ipinfo = def_info.get(def_ip_version)
        if ipinfo:
            ip = ipinfo.get('addr')
    if ip is None:
        msg = "Your host does not have an ip address on interface: %s using ip version: %s!" % (def_net_ifc, def_ip_version)
        raise excp.NoIpException(msg)
    return ip


def get_interfaces():
    interfaces = dict()
    for intfc in netifaces.interfaces():
        interface_info = dict()
        interface_addresses = netifaces.ifaddresses(intfc)
        ip6 = interface_addresses.get(netifaces.AF_INET6)
        if ip6 and len(ip6):
            #just take the first
            interface_info[settings.IPV6] = ip6[0]
        ip4 = interface_addresses.get(netifaces.AF_INET)
        if ip4 and len(ip4):
            #just take the first
            interface_info[settings.IPV4] = ip4[0]
        #there are others but this is good for now
        interfaces[intfc] = interface_info
    return interfaces


def determine_distro():
    plt = platform.platform()
    #ensure its a linux distro
    (distname, _, _) = platform.linux_distribution()
    if not distname:
        return (None, plt)
    #attempt to match it to our platforms
    found_os = None
    for (known_os, pattern) in settings.KNOWN_DISTROS.items():
        if pattern.search(plt):
            found_os = known_os
            break
    return (found_os, plt)


def extract_pip_list(fns, distro, all_pips=None):
    if not all_pips:
        all_pips = dict()
    for fn in fns:
        js = load_json(fn)
        distro_pips = js.get(distro)
        if distro_pips:
            all_pips.update(distro_pips)
    return all_pips


def get_components_order(components):
    #deep copy so components isn't messed with
    all_components = dict()
    for (name, deps) in components.items():
        all_components[name] = set(deps)
    #figure out which ones have no one depending on them
    no_deps_components = set()
    for (name, deps) in all_components.items():
        referenced = False
        for (_name, _deps) in all_components.items():
            if _name == name:
                continue
            else:
                if name in _deps:
                    referenced = True
                    break
        if not referenced:
            no_deps_components.add(name)
    if not no_deps_components:
        msg = "Components specifed have no root components, there is most likely a dependency cycle!"
        raise excp.DependencyException(msg)
    #now we have to do a quick check to ensure no component is causing a cycle
    for (root, deps) in all_components.items():
        #DFS down through the "roots" deps and there deps and so on and
        #ensure that nobody is referencing the "root" component name,
        #that would mean there is a cycle if a dependency of the "root" is.
        active_deps = list(deps)
        checked_deps = dict()
        while len(active_deps):
            dep = active_deps.pop()
            itsdeps = all_components.get(dep)
            checked_deps[dep] = True
            if root in itsdeps:
                msg = "Circular dependency between component %s and component %s!" % (root, dep)
                raise excp.DependencyException(msg)
            else:
                for d in itsdeps:
                    if d not in checked_deps and d not in active_deps:
                        active_deps.append(d)
    #now form the order
    #basically a topological sorting
    #https://en.wikipedia.org/wiki/Topological_sorting
    ordering = list()
    no_edges = set(no_deps_components)
    while len(no_edges):
        node = no_edges.pop()
        ordering.append(node)
        its_deps = all_components.get(node)
        while len(its_deps):
            name = its_deps.pop()
            referenced = False
            for (_name, _deps) in all_components.items():
                if _name == name:
                    continue
                else:
                    if name in _deps:
                        referenced = True
                        break
            if not referenced:
                no_edges.add(name)
    #should now be no edges else something bad happended
    for (_, deps) in all_components.items():
        if len(deps):
            msg = "Your specified components have at least one cycle!"
            raise excp.DependencyException(msg)
    #reverse so its in the right order for us
    ordering.reverse()
    return ordering


def extract_pkg_list(fns, distro, all_pkgs=None):
    if not all_pkgs:
        all_pkgs = dict()
    for fn in fns:
        js = load_json(fn)
        distro_pkgs = js.get(distro)
        if distro_pkgs:
            all_pkgs.update(distro_pkgs)
    return all_pkgs


def joinlinesep(*pieces):
    return os.linesep.join(pieces)


def param_replace(text, replacements, ignore_missing=False):

    if not replacements:
        return text

    if not text:
        return text

    if ignore_missing:
        LOG.debug("Performing parameter replacements (ignoring missing) on %s" % (text))
    else:
        LOG.debug("Performing parameter replacements (not ignoring missing) on %s" % (text))

    def replacer(match):
        org = match.group(0)
        name = match.group(1)
        v = replacements.get(name)
        if v is None and ignore_missing:
            v = org
        elif v is None and not ignore_missing:
            msg = "No replacement found for parameter %s" % (org)
            raise excp.NoReplacementException(msg)
        else:
            LOG.debug("Replacing [%s] with [%s]" % (org, str(v)))
        return str(v)

    return PARAM_SUB_REGEX.sub(replacer, text)


def _get_welcome_stack():
    possibles = list()
    #thank you figlet ;)
    possibles.append(r'''
  ___  ____  _____ _   _ ____ _____  _    ____ _  __
 / _ \|  _ \| ____| \ | / ___|_   _|/ \  / ___| |/ /
| | | | |_) |  _| |  \| \___ \ | | / _ \| |   | ' /
| |_| |  __/| |___| |\  |___) || |/ ___ \ |___| . \
 \___/|_|   |_____|_| \_|____/ |_/_/   \_\____|_|\_\

''')
    possibles.append(r'''
  ___  ___ ___ _  _ ___ _____ _   ___ _  __
 / _ \| _ \ __| \| / __|_   _/_\ / __| |/ /
| (_) |  _/ _|| .` \__ \ | |/ _ \ (__| ' <
 \___/|_| |___|_|\_|___/ |_/_/ \_\___|_|\_\

''')
    possibles.append(r'''
____ ___  ____ _  _ ____ ___ ____ ____ _  _
|  | |__] |___ |\ | [__   |  |__| |    |_/
|__| |    |___ | \| ___]  |  |  | |___ | \_

''')
    possibles.append(r'''
  _  ___ ___  _  _  __  ___  _   __  _  _
 / \| o \ __|| \| |/ _||_ _|/ \ / _|| |//
( o )  _/ _| | \\ |\_ \ | || o ( (_ |  (
 \_/|_| |___||_|\_||__/ |_||_n_|\__||_|\\

''')
    possibles.append(r'''
   _   ___  ___  _  __  ___ _____  _    __  _
 ,' \ / o |/ _/ / |/ /,' _//_  _/.' \ ,'_/ / //7
/ o |/ _,'/ _/ / || /_\ `.  / / / o // /_ /  ,'
|_,'/_/  /___//_/|_//___,' /_/ /_n_/ |__//_/\\

''')
    possibles.append(r'''
 _____  ___    ___    _   _  ___   _____  _____  ___    _   _
(  _  )(  _`\ (  _`\ ( ) ( )(  _`\(_   _)(  _  )(  _`\ ( ) ( )
| ( ) || |_) )| (_(_)| `\| || (_(_) | |  | (_) || ( (_)| |/'/'
| | | || ,__/'|  _)_ | , ` |`\__ \  | |  |  _  || |  _ | , <
| (_) || |    | (_( )| |`\ |( )_) | | |  | | | || (_( )| |\`\
(_____)(_)    (____/'(_) (_)`\____) (_)  (_) (_)(____/'(_) (_)

''')
    return random.choice(possibles)


def center_text(text, fill, max_len):
    centered_str = '{0:{fill}{align}{size}}'.format(text, fill=fill, align="^", size=max_len)
    return centered_str


def goodbye(worked):
    #thx cowsay
    cow = r'''
 __________
/ {top}  \
\ {message} /
 ----------
        \   {ear}__{ear}
         \  ({eye}{eye})\_______
            (__)\       )\/\
                ||----w |
                ||     ||
'''
    cow = cow.strip("\n\r")
    ear = '^'
    eye_fmt = 'o'
    if not worked:
        top = "Nooooo!"
        msg = 'Failure!'
        eye_fmt = colored("o", 'red')
        ear = colored(ear, 'red')
        header = "_" * (len(top) + 2)
        footer = "-" * (len(msg) + 2)
        msg = colored(msg, 'red', attrs=['bold'])
        top = colored(top, 'red', attrs=['bold'])
    else:
        top = "Yippie!"
        msg = 'Success!'
        header = "_" * (len(top) + 2)
        footer = "-" * (len(msg ) + 2)
        msg = colored(msg, 'green', attrs=['bold'])
        top = colored(top, 'green', attrs=['bold'])
    msg = cow.format(message=msg, eye=eye_fmt, ear=ear,
                    top=top, header=header, footer=footer)
    print(msg)


def parse_components(components):
    #none provided, init it
    if not components:
        components = list()
    adjusted_components = dict()
    for c in components:
        mtch = EXT_COMPONENT.match(c)
        if mtch:
            component_name = mtch.group(1).lower().strip()
            if component_name in settings.COMPONENT_NAMES:
                component_opts = mtch.group(2)
                components_opts_cleaned = list()
                if not component_opts:
                    pass
                else:
                    sp_component_opts = component_opts.split(",")
                    for co in sp_component_opts:
                        cleaned_opt = co.strip()
                        if cleaned_opt:
                            components_opts_cleaned.append(cleaned_opt)
                adjusted_components[component_name] = components_opts_cleaned
    return adjusted_components


def welcome(ident):
    ver_str = version.version_string()
    lower = "|"
    if ident:
        lower += ident
        lower += " "
    lower += ver_str
    lower += "|"
    welcome_header = _get_welcome_stack().strip("\n\r")
    max_line_len = len(max(welcome_header.splitlines(), key=len))
    footer = colored(settings.PROG_NICE_NAME, 'green', attrs=['bold']) + \
                ": " + colored(lower, 'blue', attrs=['bold'])
    uncolored_footer = (settings.PROG_NICE_NAME + ": " + lower)
    if max_line_len - len(uncolored_footer) > 0:
        #this format string wil center the uncolored text which
        #we will then replace
        #with the color text equivalent
        centered_str = center_text(uncolored_footer, " ", max_line_len)
        footer = centered_str.replace(uncolored_footer, footer)
    print((welcome_header + os.linesep + footer))
    return ("-", max_line_len)
