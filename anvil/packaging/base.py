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

# R0921: Abstract class not referenced
#pylint: disable=R0921

import abc
import pkg_resources

from anvil import colorizer
from anvil.components import base as component_base
from anvil import log as logging
from anvil import shell as sh
from anvil import type_utils
from anvil import utils

LOG = logging.getLogger(__name__)


class Packager(object):
    """Basic class for package management systems support.
    """
    __meta__ = abc.ABCMeta

    def __init__(self, distro, remove_default=False):
        self.distro = distro
        self.remove_default = remove_default

    def remove(self, pkg):
        should_remove = self.remove_default
        if 'removable' in pkg:
            should_remove = type_utils.make_bool(pkg['removable'])
        if not should_remove:
            return False
        self._remove(pkg)
        return True

    def pre_install(self, pkg, params=None):
        cmds = pkg.get('pre-install')
        if cmds:
            LOG.info("Running pre-install commands for package %s.", colorizer.quote(pkg['name']))
            utils.execute_template(*cmds, params=params)

    def post_install(self, pkg, params=None):
        cmds = pkg.get('post-install')
        if cmds:
            LOG.info("Running post-install commands for package %s.", colorizer.quote(pkg['name']))
            utils.execute_template(*cmds, params=params)

    @abc.abstractmethod
    def _remove(self, pkg):
        pass

    @abc.abstractmethod
    def _install(self, pkg):
        pass


OPENSTACK_PACKAGES = set([
    "cinder",
    "glance",
    "horizon",
    "keystone",
    "nova",
    "oslo.config",
    "quantum",
    "swift",
    "python-cinderclient",
    "python-glanceclient",
    "python-keystoneclient",
    "python-novaclient",
    "python-quantumclient",
    "python-swiftclient",
])


class DependencyHandler(object):
    """Basic class for handler of OpenStack dependencies.
    """
    multipip_executable = "multipip"
    # Update requirements to make them allow already installed packages
    force_frozen = True

    def __init__(self, distro, root_dir, instances):
        self.distro = distro
        self.root_dir = root_dir
        self.instances = instances

        self.deps_dir = sh.joinpths(self.root_dir, "deps")
        self.download_dir = sh.joinpths(self.deps_dir, "download")
        self.gathered_requires_filename = sh.joinpths(
            self.deps_dir, "pip-requires")
        self.forced_requires_filename = sh.joinpths(
            self.deps_dir, "forced-requires")
        self.pip_executable = str(self.distro.get_command_config('pip'))
        self.pips_to_install = []
        self.forced_packages = []
        # nopips is a list of items that fail to build from Python packages,
        # but their RPMs are available from base and epel repos
        self.nopips = []
        # these packages conflict with our deps and must be removed
        self.nopackages = []

    def prepare(self):
        LOG.info("Preparing OpenStack dependencies")
        requires_files = []
        extra_pips = []
        self.nopips = []
        for inst in self.instances:
            try:
                requires_files.extend(inst.requires_files)
            except AttributeError:
                pass
            for pkg in inst.get_option("pips") or []:
                extra_pips.append(
                    "%s%s" % (pkg["name"], pkg.get("version", "")))
            for pkg in inst.get_option("nopips") or []:
                self.nopips.append(pkg["name"])
        requires_files = filter(sh.isfile, requires_files)
        self.gather_pips_to_install(requires_files, extra_pips)
        self.clean_pip_requires(requires_files)

    def install(self):
        LOG.info("Installing OpenStack dependencies")
        self.nopackages = []
        for inst in self.instances:
            for pkg in inst.get_option("nopackages") or []:
                self.nopackages.append(pkg["name"])

    def clean_pip_requires(self, requires_files):
        # Fixup incompatible dependencies
        if not (requires_files and self.forced_packages):
            return
        utils.log_iterable(
            sorted(requires_files),
            logger=LOG,
            header="Adjusting %s pip 'requires' files" %
            (len(requires_files)))
        forced_by_key = dict((pkg.key, pkg) for pkg in self.forced_packages)
        for fn in requires_files:
            old_lines = sh.load_file(fn).splitlines()
            new_lines = []
            for line in old_lines:
                try:
                    req = pkg_resources.Requirement.parse(line)
                    new_lines.append(str(forced_by_key[req.key]))
                except:
                    # we don't force the package or it has a bad format
                    new_lines.append(line)
            contents = "# Cleaned on %s\n\n%s\n" % (
                utils.iso8601(), "\n".join(new_lines))
            sh.write_file_and_backup(fn, contents)

    def gather_pips_to_install(self, requires_files, extra_pips=[]):
        """Analyze requires_files and extra_pips.

        Updates `self.forced_packages` and `self.pips_to_install`.
        If `self.force_frozen`, update requirements to make them allow already
        installed packages.
        Writes requirements to `self.gathered_requires_filename`.
        """
        cmdline = [
            self.multipip_executable,
            "--skip-requirements-regex",
            "python.*client",
            "--pip",
            self.pip_executable
        ]
        if self.force_frozen:
            cmdline.append("--frozen")
        cmdline = cmdline + extra_pips + ["-r"] + requires_files

        output = sh.execute(*cmdline, ignore_exit_code=True)
        conflict_descr = output[1].strip()
        forced_keys = set()
        if conflict_descr:
            for line in conflict_descr.splitlines():
                LOG.warning(line)
                if line.endswith(": incompatible requirements"):
                    forced_keys.add(line.split(":", 1)[0].lower())
        self.pips_to_install = [
            pkg
            for pkg in utils.splitlines_not_empty(output[0])
            if pkg.lower() not in OPENSTACK_PACKAGES]
        sh.write_file(self.gathered_requires_filename,
                      "\n".join(self.pips_to_install))
        if not self.pips_to_install:
            LOG.error("No dependencies for OpenStack found."
                      "Something went wrong. Please check:")
            LOG.error("'%s'" % "' '".join(cmdline))
            raise RuntimeError("No dependencies for OpenStack found")

        utils.log_iterable(sorted(self.pips_to_install),
                           logger=LOG,
                           header="Full known Python dependency list")
        self.forced_packages = []
        for pip in self.pips_to_install:
            req = pkg_resources.Requirement.parse(pip)
            if req.key in forced_keys:
                self.forced_packages.append(req)
        sh.write_file(self.forced_requires_filename,
                      "\n".join(str(req) for req in self.forced_packages))

    def download_dependencies(self, ignore_installed=True, clear_cache=False):
        """Download dependencies from `$deps_dir/download-requires`.

        :param ignore_installed: do not download already installed packages
        :param clear_cache: clear `$deps_dir/cache` dir (pip can work incorrectly
            when it has a cache)
        """
        cache_dir = sh.joinpths(self.deps_dir, "cache")
        if clear_cache:
            sh.deldir(cache_dir)
        sh.mkdir(self.deps_dir, recurse=True)

        download_requires_filename = sh.joinpths(
            self.deps_dir, "download-requires")
        if ignore_installed or self.nopips:
            cmdline = [
                self.multipip_executable,
                "--pip", self.pip_executable,
            ]
            if ignore_installed:
                cmdline += [
                    "--ignore-installed",
                ]
            cmdline.extend(self.pips_to_install)
            if self.nopips:
                cmdline.append("--ignore-packages")
                cmdline.extend(self.nopips)
            output = sh.execute(*cmdline)
            pips_to_download = list(utils.splitlines_not_empty(output[0]))
        else:
            pips_to_download = self.pips_to_install
        sh.write_file(download_requires_filename,
                      "\n".join(str(req) for req in pips_to_download))

        if not pips_to_download:
            return []
        # NOTE(aababilov): pip has issues with already downloaded files
        sh.deldir(self.download_dir)
        sh.mkdir(self.download_dir, recurse=True)
        cmdline = [
            self.pip_executable,
            "install",
            "--download",
            self.download_dir,
            "--download-cache",
            cache_dir,
            "-r",
            download_requires_filename,
        ]
        out_filename = sh.joinpths(self.deps_dir, "pip-install-download.out")
        utils.log_iterable(sorted(pips_to_download), logger=LOG,
                           header="Downloading Python dependencies")
        LOG.info("You can watch progress in another terminal with")
        LOG.info("    tail -f %s" % out_filename)
        with open(out_filename, "w") as out:
            sh.execute(*cmdline, stdout_fh=out, stderrr_fh=out)
        return sh.listdir(self.download_dir, files_only=True)


class EmptyPackager(component_base.Component):
    def package(self):
        return None
