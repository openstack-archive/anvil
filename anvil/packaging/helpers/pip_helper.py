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

import pkg_resources

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


def parse_requirements(contents, adjust=False):
    lines = []
    for line in contents.splitlines():
        line = line.strip()
        if not len(line) or line.startswith('#'):
            continue
        # Don't take editables either...
        if line.lower().startswith('-e'):
            continue
        lines.append(line)
    requires = []
    for req in pkg_resources.parse_requirements(lines):
        requires.append(req)
    return requires


class Helper(object):
    # Cache of whats installed list
    _installed_cache = None

    def __init__(self, call_how):
        if not isinstance(call_how, (basestring, str)):
            self._pip_how = call_how.get_command_config('pip')
        else:
            self._pip_how = call_how

    def _list_installed(self):
        cmd = [str(self._pip_how)] + FREEZE_CMD
        (stdout, _stderr) = sh.execute(*cmd)
        return parse_requirements(stdout, True)

    @staticmethod
    def uncache():
        Helper._installed_cache = None

    def whats_installed(self):
        if Helper._installed_cache is None:
            Helper._installed_cache = self._list_installed()
        return list(Helper._installed_cache)

    def is_installed(self, name):
        if self.get_installed(name):
            return True
        return False

    def get_installed(self, name):
        whats_there = self.whats_installed()
        for whats_installed in whats_there:
            if not (name.lower() == whats_installed.key):
                continue
            return whats_installed
        return None
