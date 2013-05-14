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

from distutils import version as vr

import copy
import pkg_resources
import xmlrpclib

from anvil import log as logging
from anvil import shell as sh

LOG = logging.getLogger(__name__)

FREEZE_CMD = ['freeze', '--local']


class Requirement(object):
    def __init__(self, name, version=None):
        self.name = str(name)
        if version is not None:
            self.version = vr.LooseVersion(str(version))
        else:
            self.version = None
        self.key = self.name.lower()

    def __str__(self):
        name = str(self.name)
        if self.version is not None:
            name += "==" + str(self.version)
        return name


def _skip_requirement(line):
    # Skip blank lines or comment lines
    if not len(line):
        return True
    if line.startswith("#"):
        return True
    # Skip editables also...
    if line.lower().startswith('-e'):
        return True
    # Skip http types also...
    if line.lower().startswith('http://'):
        return True
    return False


def find_pypi_match(req, pypi_url='http://python.org/pypi'):
    try:
        pypi = xmlrpclib.ServerProxy(pypi_url)
        possibles = []
        LOG.debug("Searching pypi @ %s for %s", pypi_url, req)
        for h in pypi.search({'name': req.key}):
            if req.key == h.get('name', '').lower():
                LOG.debug("Found potential match %s", h)
                # Seem to get prefix matches back, only want exact match...
                possible = h['name']
                if 'version' in h:
                    # Less than so later comparison works... since this
                    # package can satisfy requests for versions less than
                    # or equal to itself...
                    possible += "<=%s" % (h['version'])
                possibles.append({
                    'parsed': parse_requirements(possible)[0],
                    'requirement': Requirement(h['name'], h.get('version')),
                })
        if not possibles:
            return None
        for p in possibles:
            if req in p['parsed']:
                LOG.debug("Found match in pypi: %s satisfies %s", p['parsed'], req)
                return p['requirement']
    except (IOError, xmlrpclib.Fault, xmlrpclib.Error) as e:
        LOG.warn("Scanning pypi failed: %s", e)
    return None


def parse_requirements(contents, adjust=False):
    lines = []
    for line in contents.splitlines():
        line = line.strip()
        if not _skip_requirement(line):
            lines.append(line)
    requires = []
    for req in pkg_resources.parse_requirements(lines):
        requires.append(req)
    return requires


class Helper(object):
    # Cache of whats installed
    _installed_cache = {}

    def __init__(self, call_how):
        if not isinstance(call_how, (basestring, str)):
            # Assume u are passing in a distro object
            self._pip_how = str(call_how.get_command_config('pip'))
        else:
            self._pip_how = call_how

    def _list_installed(self):
        cmd = [self._pip_how] + FREEZE_CMD
        (stdout, _stderr) = sh.execute(*cmd, run_as_root=True)
        return parse_requirements(stdout, True)

    def uncache(self):
        Helper._installed_cache.pop(self._pip_how, None)

    def whats_installed(self):
        if not (self._pip_how in Helper._installed_cache):
            Helper._installed_cache[self._pip_how] = self._list_installed()
        return copy.copy(Helper._installed_cache[self._pip_how])

    def is_installed(self, name):
        if self.get_installed(name):
            return True
        return False

    def get_installed(self, name):
        whats_there = self.whats_installed()
        wanted_package = Requirement(name)
        for whats_installed in whats_there:
            if not (wanted_package.key == whats_installed.key):
                continue
            return whats_installed
        return None
