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
from pkg_resources import Requirement

from anvil import log as logging
from anvil import shell as sh

LOG = logging.getLogger(__name__)

FREEZE_CMD = ['freeze', '--local']


# Cache of whats installed - 'uncached' as needed
_installed_cache = None


class LooseRequirement(object):
    def __init__(self, name, version=None):
        self.name = name
        if version is not None:
            self.version = vr.LooseVersion(version)
        else:
            self.version = None

    def __str__(self):
        if self.version is not None:
            return "%s (%s)" % (self.name, self.version)
        else:
            return str(self.name)

    def __contains__(self, version):
        if self.version is None:
            return True
        else:
            return version <= self.version


def uncache():
    global _installed_cache
    _installed_cache = None


def _list_installed(pip_how):
    cmd = [str(pip_how)] + FREEZE_CMD
    (stdout, _stderr) = sh.execute(*cmd)
    installed = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Don't take editables either...
        if line.startswith('-e'):
            continue
        v = None
        try:
            line_requirements = Requirement.parse(line)
            (_cmp, v) = line_requirements.specs[0]
        except (ValueError, TypeError) as e:
            LOG.warn("Unparseable pip freeze line %s: %s" % (line, e))
            continue
        installed.append(LooseRequirement(line_requirements.key, v))
    return installed


def whats_installed(pip_how):
    global _installed_cache
    if _installed_cache is None:
        _installed_cache = _list_installed(pip_how)
    return _installed_cache


def is_installed(pip_how, name, version=None):
    if get_installed(pip_how, name, version):
        return True
    return False


def get_installed(pip_how, name, version=None):
    whats_there = whats_installed(pip_how)
    for req in whats_there:
        if not (name.lower() == req.name):
            continue
        if not version:
            return req
        if version in req:
            return req
    return None
