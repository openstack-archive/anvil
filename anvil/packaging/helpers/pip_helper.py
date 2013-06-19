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

import copy
import pkg_resources

from pip import util as pip_util
from pip import req as pip_req

from anvil import log as logging
from anvil import shell as sh
from anvil import utils

LOG = logging.getLogger(__name__)

FREEZE_CMD = ['freeze', '--local']
EGGS_DETAILED = {}


def create_requirement(name, version=None):
    name = pkg_resources.safe_name(name.strip())
    if not name:
        raise ValueError("Pip requirement provided with an empty name")
    if version is not None:
        if isinstance(version, (int, float, long)):
            version = "==%s" % version
        if isinstance(version, (str, basestring)):
            if version[0] not in "=<>":
                version = "==%s" % version
        else:
            raise TypeError(
                "Pip requirement version must be a string or numeric type")
        name = "%s%s" % (name, version)
    return pkg_resources.Requirement.parse(name)


def get_directory_details(path):
    if not sh.isdir(path):
        raise IOError("Can not detail non-existent directory %s" % (path))

    # Check if we already got the details of this dir previously
    path = sh.abspth(path)
    cache_key = "d:%s" % (sh.abspth(path))
    if cache_key in EGGS_DETAILED:
        return EGGS_DETAILED[cache_key]

    req = pip_req.InstallRequirement.from_line(path)
    req.source_dir = path
    req.run_egg_info()

    dependencies = []
    for d in req.requirements():
        if not d.startswith("-e") and d.find("#"):
            d = d.split("#")[0]
        d = d.strip()
        if d:
            dependencies.append(d)

    details = {
        'req': req.req,
        'dependencies': dependencies,
        'name': req.name,
        'pkg_info': req.pkg_info(),
        'dependency_links': req.dependency_links,
        'version': req.installed_version,
    }

    EGGS_DETAILED[cache_key] = details
    return details


def get_archive_details(filename):
    if not sh.isfile(filename):
        raise IOError("Can not detail non-existent file %s" % (filename))

    # Check if we already got the details of this file previously
    cache_key = "f:%s:%s" % (sh.basename(filename), sh.getsize(filename))
    if cache_key in EGGS_DETAILED:
        return EGGS_DETAILED[cache_key]

    # Get pip to get us the egg-info.
    with utils.tempdir() as td:
        filename = sh.copy(filename, sh.joinpths(td, sh.basename(filename)))
        extract_to = sh.mkdir(sh.joinpths(td, 'build'))
        pip_util.unpack_file(filename, extract_to, content_type='', link='')
        details = get_directory_details(extract_to)

    EGGS_DETAILED[cache_key] = details
    return details


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
        (stdout, _stderr) = sh.execute(cmd)
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
        wanted_package = create_requirement(name)
        for whats_installed in whats_there:
            if not (wanted_package.key == whats_installed.key):
                continue
            return whats_installed
        return None
