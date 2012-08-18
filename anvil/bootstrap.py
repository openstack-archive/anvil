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
#    under the License..

import contextlib
import os
import platform
import random
import re
import subprocess
import sys
import tempfile
import time
import urllib2

# These are safe to import without bringing in non-core
# python dependencies...
from anvil import version

BOOT_STRAP_FN = os.path.join(os.path.expanduser("~"), ".anvil_strapped")
RH_EPEL_URLS = [
    'http://mirror.cogentco.com/pub/linux/epel/6/i386',
    "http://epel.mirror.freedomvoice.com/6/i386",
    'http://mirrors.kernel.org/fedora-epel/6/i386',
]
URL_TIMEOUT = 5


def tiny_p(cmd, capture=True):
    # Darn python 2.6 doesn't have check_output (argggg)
    stdout = subprocess.PIPE
    stderr = subprocess.PIPE
    if not capture:
        stdout = None
        stderr = None
    sp = subprocess.Popen(cmd, stdout=stdout,
                    stderr=stderr, stdin=None)
    (out, err) = sp.communicate()
    if sp.returncode not in [0]:
        raise RuntimeError("Failed running %s [rc=%s] (%s, %s)" 
                            % (cmd, sp.returncode, out, err))
    return (out, err)


def _write_msg(msg):
    sys.stderr.write("%s\n" % (msg))


def _write_warn(msg):
    _write_msg("WARNING: %s" % (msg))


def _strap_nodejs(repo_fn="/etc/yum.repos.d/epel-nodejs.repo"):
    _write_msg("Making node.js installable by yum by creating %s" % (repo_fn))

    # For now this will work until it shows up in epel
    node_js_repo = '''# Place this file in your /etc/yum.repos.d/ directory

[epel-nodejs]
name=node.js stack in development: runtime and several npm packages
baseurl=http://repos.fedorapeople.org/repos/lkundrak/nodejs/epel-6/$basearch/
enabled=1
skip_if_unavailable=1
gpgcheck=0
'''

    if not os.path.isfile(repo_fn):
        with open(repo_fn, 'w') as fh:
            fh.write(node_js_repo)


def _strap_epel():
    exceptions = []
    fetched = False
    _write_msg("Installing EPEL repositories...")
    for u in RH_EPEL_URLS:
        try:
            _write_msg("Scraping %s for the EPEL release rpm filename." % (u))
            with contextlib.closing(urllib2.urlopen(u, timeout=URL_TIMEOUT)) as uh:
                rel = re.search("epel-release(.*?)[.]rpm", uh.read(), re.I)
            if rel:
                with tempfile.NamedTemporaryFile(suffix=".rpm") as th:
                    du = "%s/%s" % (u, rel.group(0).strip())
                    _write_msg("Trying EPEL release rpm from url: %s" % (du))
                    with contextlib.closing(urllib2.urlopen(du, timeout=URL_TIMEOUT)) as uh:
                        th.write(uh.read())
                        th.flush()
                    try:
                        tiny_p(['yum', 'install', '-y', th.name])
                        fetched = True
                    except RuntimeError as e2:
                        if 'nothing to do' in str(e2).lower():
                            # This seems to return non-zero even if it worked..
                            fetched = True
                        else:
                            exceptions.append(e2)
                    if fetched:
                        break
        except urllib2.URLError as e:
            exceptions.append(e)
    if exceptions and not fetched:
        raise exceptions[-1]


def _strap_redhat_based(distname):
    if distname in ['redhat', 'centos']:
        _strap_epel()
        _strap_nodejs()
        pkgs = ['gcc', 'git', 'pylint', 'python', 'python-netifaces', 
                'python-pep8', 'python-pip', 'python-progressbar', 'PyYAML',
                'python-ordereddict']
        pips = ['termcolor', 'iniparse']
    else:
        pkgs = ['gcc', 'git', 'pylint', 'python', 'python-netifaces', 
                'python-pep8', 'python-pip', 'python-progressbar',
                'PyYAML', 'python-iniparse']
        pips = ['termcolor']

    _write_msg("Installing %s distribution packages..." % (pkgs))
    cmd = ['yum', 'install', '-y']
    cmd.extend(pkgs)
    tiny_p(cmd)

    _write_msg("Installing %s pypi packages..." % (pips))
    cmd = ['pip-python', 'install']
    cmd.extend(pips)
    tiny_p(cmd)


def _strap_deb_based(distname):
    pkgs = ['gcc', 'git', 'pep8', 'pylint', 'python', 'python-dev',
            'python-iniparse', 'python-pip', 'python-progressbar', 'python-yaml']
    pips = ['netifaces', 'termcolor']

    _write_msg("Installing %s distribution packages..." % (pkgs))
    cmd = ['apt-get', '--yes', 'install']
    cmd.extend(pkgs)
    tiny_p(cmd)

    _write_msg("Installing %s pypi packages..." % (pips))
    cmd = ['pip', 'install']
    cmd.extend(pips)
    tiny_p(cmd)


def is_supported():
    (distname, _version, _id) = platform.linux_distribution(full_distribution_name=False)
    distname = distname.lower().strip()
    if distname in ['redhat', 'fedora', 'ubuntu', 'debian', 'centos']:
        return True
    return False


def _is_strapped():
    if not os.path.isfile(BOOT_STRAP_FN):
        return False
    booted_ver = ''
    with open(BOOT_STRAP_FN, 'r') as fh:
        booted_ver = fh.read()
    if booted_ver.strip().lower() == version.version_string().lower():
        return True
    return False


def strap():
    if _is_strapped():
        return False
    _write_msg("Bootstrapping anvil...")
    _write_msg("Please wait...")
    (distname, _version, _id) = platform.linux_distribution(full_distribution_name=False)
    distname = distname.lower().strip()
    strap_functor = None
    if distname in ['redhat', 'fedora', 'centos']:
        strap_functor = _strap_redhat_based
    elif distname in ['ubuntu', 'debian']:
        strap_functor = _strap_deb_based
    if not strap_functor:
        _write_warn('Anvil does not know how to bootstrap on platform: %s' % (platform.platform()))
    else:
        strap_functor(distname)
        _write_msg("Bootstrapped anvil for linux distribution %s..." % (distname))
        with open(BOOT_STRAP_FN, 'w') as fh:
            fh.write("%s\n" % (version.version_string()))
    return True
