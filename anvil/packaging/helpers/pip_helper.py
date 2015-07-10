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
import glob
import pkg_resources
import re
import sys
import tempfile
import threading

from pip import download as pip_download
from pip import req as pip_req
from pip import utils as pip_util

import pkginfo
import six

from anvil import log as logging
from anvil import shell as sh
from anvil import utils

LOG = logging.getLogger(__name__)

# Caches and there associated locks...
REQUIREMENT_FILE_CACHE = {}
REQUIREMENT_FILE_CACHE_LOCK = threading.RLock()
EGGS_DETAILED = {}
EGGS_DETAILED_LOCK = threading.RLock()

PYTHON_KEY_VERSION_RE = re.compile("^(.+)-([0-9][0-9.a-zA-Z]*)$")
PIP_VERSION = pkg_resources.get_distribution('pip').version
PIP_EXECUTABLE = sh.which_first(['pip', 'pip-python'])


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


def _split(line):
    if line.startswith('-e') or line.startswith('--editable'):
        if line.startswith('-e'):
            line = line[2:].strip()
        else:
            line = line[len('--editable'):].strip().lstrip('=')
        if line:
            return ('-e', line)
    return (None, line)


def extract(line):
    if line.startswith('-e') or line.startswith('--editable'):
        if line.startswith('-e'):
            line = line[2:].strip()
        else:
            line = line[len('--editable'):].strip().lstrip('=')
        req = pip_req.InstallRequirement.from_editable(line, comes_from="??")
    else:
        req = pip_req.InstallRequirement.from_line(line, comes_from="??")
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


def get_directory_details(path, pbr_version=None):
    if not sh.isdir(path):
        raise IOError("Can not detail non-existent directory %s" % (path))

    # Check if we already got the details of this dir previously
    with EGGS_DETAILED_LOCK:
        path = sh.abspth(path)
        cache_key = "d:%s" % (sh.abspth(path))
        if cache_key in EGGS_DETAILED:
            return EGGS_DETAILED[cache_key]

        details = None
        skip_paths = [
            sh.joinpths(path, "PKG-INFO"),
            sh.joinpths(path, "EGG-INFO"),
        ]
        skip_paths.extend(glob.glob(sh.joinpths(path, "*.egg-info")))
        if any(sh.exists(a_path) for a_path in skip_paths):
            # Some packages seem to not support the 'egg_info' call and
            # provide there own path/file that contains this information
            # already, so just use it if we can get at it...
            #
            # Ie for pyyaml3.x:
            #
            # error: invalid command 'egg_info'
            details = pkginfo.Develop(path)
        if not details or not details.name:
            cmd = [sys.executable, 'setup.py', 'egg_info']
            if pbr_version:
                env_overrides = {
                    "PBR_VERSION": str(pbr_version),
                }
            else:
                env_overrides = {}
            sh.execute(cmd, cwd=path, env_overrides=env_overrides)
            details = pkginfo.get_metadata(path)
        if not details or not details.name:
            raise RuntimeError("No egg detail information discovered"
                               " at '%s'" % path)

        egg_details = {
            'req': create_requirement(details.name, version=details.version),
        }
        for attr_name in ['description', 'author',
                          'version', 'name', 'summary']:
            egg_details[attr_name] = getattr(details, attr_name)
        for attr_name in ['description', 'author', 'summary']:
            attr_value = egg_details[attr_name]
            if isinstance(attr_value, six.text_type):
                # Fix any unicode which will cause unicode decode failures...
                # versions or names shouldn't be unicode, and the rest
                # we don't really care about being unicode (since its
                # just used for logging right now anyway...).
                #
                # The reason this is done is that 'elasticsearch' seems to
                # have a unicode author name, and that causes the log_object
                # to blowup, so just avoid that by replacing this information
                # in the first place.
                egg_details[attr_name] = attr_value.encode("ascii",
                                                           errors='replace')

        LOG.debug("Extracted '%s' egg detail information:", path)
        utils.log_object(egg_details, logger=LOG, level=logging.DEBUG)

        EGGS_DETAILED[cache_key] = egg_details
        return egg_details


def drop_caches():
    with EGGS_DETAILED_LOCK:
        EGGS_DETAILED.clear()
    with REQUIREMENT_FILE_CACHE_LOCK:
        REQUIREMENT_FILE_CACHE.clear()


def get_archive_details(filename, pbr_version=None):
    if not sh.isfile(filename):
        raise IOError("Can not detail non-existent file %s" % (filename))

    # Check if we already got the details of this file previously
    with EGGS_DETAILED_LOCK:
        cache_key = "f:%s:%s" % (sh.basename(filename), sh.getsize(filename))
        if cache_key in EGGS_DETAILED:
            return EGGS_DETAILED[cache_key]

        # Get pip to get us the egg-info.
        with utils.tempdir() as td:
            filename = sh.copy(filename, sh.joinpths(td, sh.basename(filename)))
            extract_to = sh.mkdir(sh.joinpths(td, 'build'))
            pip_util.unpack_file(filename, extract_to, content_type='', link='')
            egg_details = get_directory_details(extract_to,
                                                pbr_version=pbr_version)

        EGGS_DETAILED[cache_key] = egg_details
        return egg_details


def parse_requirements(contents):
    with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_fh:
        tmp_fh.write(contents)
        tmp_fh.write("\n")
        tmp_fh.flush()
        return read_requirement_files([tmp_fh.name])


def read_requirement_files(files):
    pip_requirements = []
    session = pip_download.PipSession()
    for filename in files:
        if sh.isfile(filename):
            cache_key = "f:%s:%s" % (sh.abspth(filename), sh.getsize(filename))
            with REQUIREMENT_FILE_CACHE_LOCK:
                try:
                    reqs = REQUIREMENT_FILE_CACHE[cache_key]
                except KeyError:
                    LOG.debug('Parsing requirements from %s', filename)
                    with open(filename, 'rb') as fh:
                        for line in fh:
                            LOG.debug(">> %s", line.strip())
                    reqs = tuple(pip_req.parse_requirements(filename,
                                                            session=session))
                    REQUIREMENT_FILE_CACHE[cache_key] = reqs
                pip_requirements.extend(reqs)
    return (pip_requirements,
            [req.req for req in pip_requirements])


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
    for p in pips_to_download:
        for p_seg in _split(p):
            if p_seg:
                cmdline.append(p_seg)
    sh.execute_save_output(cmdline, output_filename)
