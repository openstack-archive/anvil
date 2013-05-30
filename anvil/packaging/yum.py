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

import datetime
import sys

from anvil import exceptions as excp
from anvil import log as logging
from anvil.packaging import base
from anvil import shell as sh
from anvil import utils

from anvil.packaging.helpers import yum_helper

LOG = logging.getLogger(__name__)

YUM_CMD = ['yum']
YUM_INSTALL = ["install", "-y", "-t"]
YUM_REMOVE = ['erase', '-y', "-t"]


# TODO(aababilov): use it in `Requires:' at YumDependencyHandler
def extract_requirement(pkg_info):
    p_name = pkg_info.get('name', '')
    p_name = p_name.strip()
    if not p_name:
        raise ValueError("Yum requirement provided with an empty name")
    p_version = pkg_info.get('version')
    if p_version is not None:
        if isinstance(p_version, (int, float, long)):
            p_version = str(p_version)
        if not isinstance(p_version, (str, basestring)):
            raise TypeError("Yum requirement version must be a string or numeric type")
    return yum_helper.Requirement(p_name, p_version)


class MultiplePackageSolutions(excp.DependencyException):
    pass


class YumPackager(base.Packager):
    def __init__(self, distro, remove_default=False):
        super(YumPackager, self).__init__(distro, remove_default)
        self.helper = yum_helper.Helper()

    def _execute_yum(self, cmd, **kargs):
        yum_cmd = YUM_CMD + cmd
        return sh.execute(*yum_cmd, run_as_root=True,
                          check_exit_code=True, **kargs)

    def direct_install(self, filename):
        cmd = YUM_INSTALL + [filename]
        self._execute_yum(cmd)

    def _remove_special(self, name, info):
        return False

    def _remove(self, pkg):
        req = extract_requirement(pkg)
        whats_there = self.helper.get_installed(req.name)
        matched = False
        if req.version is None and len(whats_there):
            # Always matches...
            matched = True
        else:
            for p in whats_there:
                if p.verEQ(req.package):
                    matched = True
        if not len(whats_there):
            # Nothing installed
            return
        if not matched:
            # Warn that incompat. version could be uninstalled
            LOG.warn("Removing package named %s even though %s packages with different versions exist",
                     req, len(whats_there))
        if self._remove_special(req.name, pkg):
            return
        # Not removing specific version, this could
        # cause problems but should be good enough until
        # it does cause problems...
        cmd = YUM_REMOVE + [req.name]
        self._execute_yum(cmd)

    def pre_install(self, pkg, params=None):
        """pre-install is handled in openstack-deps %pre script.
        """
        pass

    def post_install(self, pkg, params=None):
        """post-install is handled in openstack-deps %post script.
        """
        pass


class YumDependencyHandler(base.DependencyHandler):
    OPENSTACK_DEPS_PACKAGE_NAME = "openstack-deps"
    OPENSTACK_EPOCH = 2
    py2rpm_executable = sh.which("py2rpm", ["multipip"])

    def __init__(self, distro, root_dir, instances):
        super(YumDependencyHandler, self).__init__(distro, root_dir, instances)
        self.rpmbuild_dir = sh.joinpths(self.deps_dir, "rpmbuild")
        self.deps_repo_dir = sh.joinpths(self.deps_dir, "openstack-deps")
        self.deps_src_repo_dir = sh.joinpths(self.deps_dir, "openstack-deps-sources")
        self.anvil_repo_filename = sh.joinpths(self.deps_dir, "anvil.repo")

    def _epoch_list(self):
        return [
            "--epoch-list",
        ] + ["%s==%s" % (name, self.OPENSTACK_EPOCH) for name in self.python_names]

    def package(self):
        super(YumDependencyHandler, self).package()
        self._write_all_deps_package()
        self._build_dependencies()
        self._build_openstack()
        self._create_deps_repo()

    def _write_all_deps_package(self):
        spec_filename = sh.joinpths(
            self.rpmbuild_dir,
            "SPECS",
            "%s.spec" % self.OPENSTACK_DEPS_PACKAGE_NAME)

        for dirname in (self.rpmbuild_dir,
                        self.deps_repo_dir,
                        self.deps_src_repo_dir):
            sh.deldir(dirname)
            sh.mkdir(dirname, recurse=True)

        today = datetime.date.today()
        spec_content = """Name: %s
Version: %s.%s.%s
Release: 0
License: Apache 2.0
Summary: Python dependencies for OpenStack
BuildArch: noarch

""" % (self.OPENSTACK_DEPS_PACKAGE_NAME, today.year, today.month, today.day)

        packages = {}
        for inst in self.instances:
            try:
                for pack in inst.packages:
                    packages[pack["name"]] = pack
            except AttributeError:
                pass

        scripts = {}
        script_map = {
            "pre-install": "%pre",
            "post-install": "%post",
            "pre-uninstall": "%preun",
            "post-uninstall": "%postun",
        }
        for pack_name in sorted(packages.iterkeys()):
            pack = packages[pack_name]
            spec_content += "Requires: %s\n" % pack["name"]
            for script_name in script_map.iterkeys():
                try:
                    script_list = pack[script_name]
                except (KeyError, ValueError):
                    continue
                script_body = scripts.get(script_name, "")
                script_body = "%s\n# %s\n" % (script_body, pack_name)
                for script in script_list:
                    try:
                        line = " ".join(
                            sh.shellquote(word)
                            for word in script["cmd"])
                    except (KeyError, ValueError):
                        continue
                    if script.get("ignore_failure"):
                        ignore = " 2>/dev/null || true"
                    else:
                        ignore = ""
                    script_body = "".join((
                        script_body,
                        line,
                        ignore,
                        "\n"))
                scripts[script_name] = script_body

        spec_content += "\n%description\n\n"
        for script_name in sorted(script_map.iterkeys()):
            try:
                script_body = scripts[script_name]
            except KeyError:
                pass
            else:
                spec_content = "%s\n%s\n%s\n" % (
                    spec_content,
                    script_map[script_name],
                    script_body)

        spec_content += "\n%files\n"
        sh.write_file(spec_filename, spec_content)
        cmdline = [
            "rpmbuild", "-ba",
            "--define", "_topdir %s" % self.rpmbuild_dir,
            spec_filename,
        ]
        LOG.info("Building %s RPM" % self.OPENSTACK_DEPS_PACKAGE_NAME)
        sh.execute(*cmdline)

    def _build_dependencies(self):
        package_files = self.download_dependencies()
        if not package_files:
            LOG.info("No RPM packages of OpenStack dependencies to build")
            return
        utils.log_iterable(sorted(package_files), logger=LOG,
                           header="Building RPM packages from files")
        cmdline = [
            self.py2rpm_executable,
            "--rpm-base",
            self.rpmbuild_dir,
        ] + self._epoch_list() + ["--"] + package_files
        out_filename = sh.joinpths(self.deps_dir, "py2rpm.deps.out")
        LOG.info("You can watch progress in another terminal with")
        LOG.info("    tail -f %s" % out_filename)
        with open(out_filename, "w") as out:
            try:
                sh.execute(*cmdline, stdout_fh=out, stderr_fh=out)
            except excp.ProcessExecutionError:
                LOG.error("Some packages failed to build.")
                LOG.error("That's usually not a big deal,"
                          " so, you can ignore this fact")

    def _build_openstack(self):
        utils.log_iterable(sorted(self.package_dirs), logger=LOG,
                           header="Building RPM packages for directories")
        cmdline = [
            self.py2rpm_executable,
            "--rpm-base",
            self.rpmbuild_dir,
        ] + self._epoch_list() + ["--"] + self.package_dirs
        out_filename = sh.joinpths(self.deps_dir, "py2rpm.openstack.out")
        LOG.info("You can watch progress in another terminal with")
        LOG.info("    tail -f %s" % out_filename)
        with open(out_filename, "w") as out:
            sh.execute(*cmdline, stdout_fh=out, stderr_fh=out)

    def _create_deps_repo(self):
        for filename in sh.listdir(sh.joinpths(self.rpmbuild_dir, "RPMS"),
                                   recursive=True, files_only=True):
            sh.move(filename, self.deps_repo_dir, force=True)
        for filename in sh.listdir(sh.joinpths(self.rpmbuild_dir, "SRPMS"),
                                   recursive=True, files_only=True):
            sh.move(filename, self.deps_src_repo_dir, force=True)
        for repo_dir in self.deps_repo_dir, self.deps_src_repo_dir:
            cmdline = ["createrepo", repo_dir]
            LOG.info("Creating repo at %s" % repo_dir)
            sh.execute(*cmdline)
        LOG.info("Writing anvil.repo to %s" % self.anvil_repo_filename)
        (_fn, content) = utils.load_template('packaging', 'anvil.repo')
        params = {"baseurl_bin": "file://%s" % self.deps_repo_dir,
                  "baseurl_src": "file://%s" % self.deps_src_repo_dir}
        sh.write_file(
            self.anvil_repo_filename, utils.expand_template(content, params))
        
    def _create_openstack_packages_list(self):
        cmdline = [self.py2rpm_executable, "--convert"] + self.python_names
        rpm_names = []
        # run as root since /tmp/pip-build-root must be owned by root
        for name in sh.execute(*cmdline, run_as_root=True)[0].splitlines():
            # name is "Requires: rpm-name"
            try:
                rpm_names.append(name.split(":")[1].strip())
            except IndexError:
                pass
        return rpm_names

    def install(self):
        super(YumDependencyHandler, self).install()
        with sh.Rooted(True):
            sh.copy(self.anvil_repo_filename, "/etc/yum.repos.d/")
        cmdline = ["yum", "erase", "-y", self.OPENSTACK_DEPS_PACKAGE_NAME]
        cmdline.extend(self.nopackages)
        sh.execute(*cmdline, run_as_root=True, ignore_exit_code=True,
                   stdout_fh=sys.stdout, stderr_fh=sys.stderr)
        cmdline = ["yum", "clean", "all"]
        sh.execute(*cmdline, run_as_root=True)

        cmdline = ["yum", "install", "-y", self.OPENSTACK_DEPS_PACKAGE_NAME]
        sh.execute(*cmdline, run_as_root=True,
                   stdout_fh=sys.stdout, stderr_fh=sys.stderr)

        rpm_names = self._create_openstack_packages_list()
        cmdline = ["yum", "install", "-y"] + rpm_names
        sh.execute(*cmdline, run_as_root=True,
                   stdout_fh=sys.stdout, stderr_fh=sys.stderr)
        
    def uninstall(self):
        super(YumDependencyHandler, self).uninstall()
        rpm_names = self._create_openstack_packages_list()
        cmdline = ["yum", "remove", "--remove-leaves", "-y"] + rpm_names
        sh.execute(*cmdline, run_as_root=True,
                   stdout_fh=sys.stdout, stderr_fh=sys.stderr)
        
