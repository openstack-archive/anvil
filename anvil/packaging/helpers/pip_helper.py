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

from distutils import version as dist_version
import pkg_resources
import re

from pip import req as pip_req

try:
    from pip import util as pip_util
except ImportError:
    # pip >=6 changed this location for some reason...
    from pip import utils as pip_util

from anvil import log as logging
from anvil import shell as sh
from anvil import utils

LOG = logging.getLogger(__name__)

EGGS_DETAILED = {}
PYTHON_KEY_VERSION_RE = re.compile("^(.+)-([0-9][0-9.a-zA-Z]*)$")
PIP_VERSION = pkg_resources.get_distribution('pip').version
PIP_EXECUTABLE = sh.which_first(['pip', 'pip-python'])
OPENSTACK_TARBALLS_RE = re.compile(r'http://tarballs.openstack.org/([^/]+)/')
SKIP_LINES = ('#', '-e', '-f', 'http://', 'https://')


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


def extract(line):
    req = pip_req.InstallRequirement.from_line(line)
    # NOTE(aababilov): req.req.key can look like oslo.config-1.2.0a2,
    # so, split it
    if req.req:
        match = PYTHON_KEY_VERSION_RE.match(req.req.key)
        if match:
            req.req = pkg_resources.Requirement.parse(
                "%s>=%s" % (match.group(1), match.group(2)))
    return req


def extract_requirement(line):
    req = extract(line)
    return req.req


def get_directory_details(path):
    if not sh.isdir(path):
        raise IOError("Can not detail non-existent directory %s" % (path))

    # Check if we already got the details of this dir previously
    path = sh.abspth(path)
    cache_key = "d:%s" % (sh.abspth(path))
    if cache_key in EGGS_DETAILED:
        return EGGS_DETAILED[cache_key]

    req = extract(path)
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


def drop_caches():
    EGGS_DETAILED.clear()


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
    return not len(line) or any(line.startswith(a) for a in SKIP_LINES)


def parse_requirements(contents, adjust=False):
    lines = []
    for line in contents.splitlines():
        line = line.strip()
        if 'http://' in line:
            m = OPENSTACK_TARBALLS_RE.search(line)
            if m:
                line = m.group(1)
        if not _skip_requirement(line):
            lines.append(line)
    return pkg_resources.parse_requirements(lines)


def read_requirement_files(files):
    result = []
    for filename in files:
        if sh.isfile(filename):
            LOG.debug('Parsing requirements from %s', filename)
            with open(filename) as f:
                result.extend(parse_requirements(f.read()))
    return result


def download_dependencies(download_dir, pips_to_download, output_filename):
    if not pips_to_download:
        return
    # NOTE(aababilov): pip has issues with already downloaded files
    if sh.isdir(download_dir):
        for filename in sh.listdir(download_dir, files_only=True):
            sh.unlink(filename)
    else:
        sh.mkdir(download_dir)
    # Clean out any previous paths that we don't want around.
    build_path = sh.joinpths(download_dir, ".build")
    if sh.isdir(build_path):
        sh.deldir(build_path)
    sh.mkdir(build_path)
    # Ensure certain directories exist that we want to exist (but we don't
    # want to delete them run after run).
    cache_path = sh.joinpths(download_dir, ".cache")
    if not sh.isdir(cache_path):
        sh.mkdir(cache_path)
    cmdline = [
        PIP_EXECUTABLE, '-v',
        'install', '-I', '-U',
        '--download', download_dir,
        '--build', build_path,
        '--download-cache', cache_path,
    ]
    # Don't download wheels...
    #
    # See: https://github.com/pypa/pip/issues/1439
    if dist_version.StrictVersion(PIP_VERSION) >= dist_version.StrictVersion('1.5'):
        cmdline.append("--no-use-wheel")
    cmdline.extend([str(p) for p in pips_to_download])
    sh.execute_save_output(cmdline, output_filename)
