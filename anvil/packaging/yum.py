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

import collections
import pkg_resources
import sys

from datetime import datetime

from anvil import colorizer
from anvil import env
from anvil import log as logging
from anvil.packaging import base
from anvil.packaging.helpers import pip_helper
from anvil.packaging.helpers import yum_helper
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils

LOG = logging.getLogger(__name__)


class YumInstallHelper(base.InstallHelper):
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
    py2rpm_executable = sh.which("py2rpm", ["tools/"])
    REPO_FN = "anvil.repo"
    YUM_REPO_DIR = "/etc/yum.repos.d/"
    BANNED_PACKAGES = [
        'distribute',
        'setuptools',
    ]

    def __init__(self, distro, root_dir, instances):
        super(YumDependencyHandler, self).__init__(distro, root_dir, instances)
        self.rpmbuild_dir = sh.joinpths(self.deps_dir, "rpmbuild")
        self.deps_repo_dir = sh.joinpths(self.deps_dir, "openstack-deps")
        self.deps_src_repo_dir = sh.joinpths(self.deps_dir, "openstack-deps-sources")
        self.anvil_repo_filename = sh.joinpths(self.deps_dir, self.REPO_FN)
        # Track what file we create so they can be cleaned up on uninstall.
        trace_fn = tr.trace_filename(root_dir, 'deps')
        self.tracewriter = tr.TraceWriter(trace_fn, break_if_there=False)
        self.tracereader = tr.TraceReader(trace_fn)
        self.helper = yum_helper.Helper()

    def py2rpm_start_cmdline(self):
        cmdline = [
            self.py2rpm_executable,
            "--rpm-base",
            self.rpmbuild_dir,
        ]
        if self.python_names:
            cmdline += [
               "--epoch-map",
            ] + ["%s==%s" % (name, self.OPENSTACK_EPOCH)
                 for name in self.python_names]
        package_map = self.distro._dependency_handler.get("package_map", {})
        if package_map:
            cmdline += [
                "--package-map",
            ] + ["%s==%s" % (key, value)
                 for key, value in package_map.iteritems()]
        arch_dependent = self.distro._dependency_handler.get(
            "arch_dependent", [])
        if arch_dependent:
            cmdline += [
                "--arch-dependent",
            ] + arch_dependent
        return cmdline

    def package(self):
        super(YumDependencyHandler, self).package()
        self._write_all_deps_package()
        self._build_dependencies()
        self._build_openstack()
        self._create_deps_repo()

    def _get_yum_available(self):
        yum_map = {}
        for pkg in self.helper.get_available():
            for provides in pkg.provides:
                pkg_info = (pkg.version, pkg.repo)
                yum_map.setdefault(provides[0], set()).add(pkg_info)
        return yum_map

    @staticmethod
    def _find_yum_match(yum_map, req, rpm_name):
        yum_versions = yum_map.get(rpm_name, [])
        for (version, repo) in yum_versions:
            if version in req:
                return (version, repo)
        return (None, None)

    def filter_download_requires(self):
        yum_map = self._get_yum_available()
        nopips = [pkg_resources.Requirement.parse(name).key
                  for name in self.python_names]

        pips_to_download = []
        req_to_install = [pkg_resources.Requirement.parse(pkg)
                          for pkg in self.pips_to_install]
        req_to_install = [req for req in req_to_install
                          if req.key not in nopips]

        requested_names = [req.key for req in req_to_install]
        rpm_to_install = self._convert_names_python2rpm(requested_names)

        satisfied_list = []
        for (req, rpm_name) in zip(req_to_install, rpm_to_install):
            (version, repo) = self._find_yum_match(yum_map, req, rpm_name)
            if not repo:
                pips_to_download.append(str(req))
            else:
                satisfied_list.append((req, rpm_name, version, repo))

        if satisfied_list:
            # Organize by repo
            repos = collections.defaultdict(list)
            for (req, rpm_name, version, repo) in satisfied_list:
                repos[repo].append("%s as %s-%s" % (req, rpm_name, version))
            for r in sorted(repos.keys()):
                header = ("%s Python packages are already available "
                          "as RPMs from repository %s")
                header = header % (len(repos[r]), colorizer.quote(r))
                utils.log_iterable(sorted(repos[r]), logger=LOG, header=header)
        return pips_to_download

    @staticmethod
    def _get_component_name(pkg_dir):
        return sh.basename(sh.dirname(pkg_dir))

    def _write_all_deps_package(self):
        spec_filename = sh.joinpths(
            self.rpmbuild_dir,
            "SPECS",
            "%s.spec" % self.OPENSTACK_DEPS_PACKAGE_NAME)

        # Clean out previous dirs.
        for dirname in (self.rpmbuild_dir, self.deps_repo_dir,
                        self.deps_src_repo_dir):
            sh.deldir(dirname)
            sh.mkdirslist(dirname, tracewriter=self.tracewriter)

        def get_version_release():
            right_now = datetime.now()
            components = [
                str(right_now.year),
                str(right_now.month),
                str(right_now.day),
            ]
            return (".".join(components), right_now.strftime("%s"))

        (version, release) = get_version_release()
        spec_content = """Name: %s
Version: %s
Release: %s
License: Apache 2.0
Summary: OpenStack dependencies
BuildArch: noarch

""" % (self.OPENSTACK_DEPS_PACKAGE_NAME, version, release)

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
            cont = [spec_content, "Requires: ", pack["name"]]
            version = pack.get("version")
            if version:
                cont.append(" ")
                cont.append(version)
            cont.append("\n")
            spec_content = "".join(cont)
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
        sh.write_file(spec_filename, spec_content,
                      tracewriter=self.tracewriter)
        cmdline = [
            "rpmbuild", "-ba",
            "--define", "_topdir %s" % self.rpmbuild_dir,
            spec_filename,
        ]
        LOG.info("Building %s RPM" % self.OPENSTACK_DEPS_PACKAGE_NAME)
        sh.execute(cmdline)

    def _build_dependencies(self):
        (pips_downloaded, package_files) = self.download_dependencies()

        # Analyze what was downloaded and eject things that were downloaded
        # by pip as a dependency of a download but which we do not want to
        # build or can satisfy by other means
        no_pips = [pkg_resources.Requirement.parse(name).key
                   for name in self.python_names]
        no_pips.extend(self.BANNED_PACKAGES)
        yum_map = self._get_yum_available()
        pips_keys = set([p.key for p in pips_downloaded])

        def filter_package_files(package_files):
            package_reqs = []
            package_keys = []
            for filename in package_files:
                package_details = pip_helper.get_archive_details(filename)
                package_reqs.append(package_details['req'])
                package_keys.append(package_details['req'].key)
            package_rpm_names = self._convert_names_python2rpm(package_keys)
            filtered_files = []
            for (filename, req, rpm_name) in zip(package_files, package_reqs,
                                                 package_rpm_names):
                if req.key in no_pips:
                    LOG.info(("Dependency %s was downloaded additionally "
                             "but it is disallowed."), req)
                    continue
                if req.key in pips_keys:
                    filtered_files.append(filename)
                    continue
                # See if pip tried to download it but we already can satisfy
                # it via yum and avoid building it in the first place...
                (version, repo) = self._find_yum_match(yum_map, req, rpm_name)
                if not repo:
                    filtered_files.append(filename)
                else:
                    LOG.info(("Dependency %s was downloaded additionally "
                             "but it can be satisfied by %s from repository "
                             "%s instead."), req, colorizer.quote(rpm_name),
                             colorizer.quote(repo))
            return filtered_files

        LOG.info("Filtering %s downloaded files.", len(package_files))
        package_files = filter_package_files(package_files)
        if not package_files:
            LOG.info("No RPM packages of OpenStack dependencies to build")
            return
        package_base_names = [sh.basename(f) for f in package_files]
        utils.log_iterable(sorted(package_base_names), logger=LOG,
                           header=("Building %s dependency RPM"
                                   " packages") % (len(package_files)))
        with utils.progress_bar(name='Building',
                                max_am=len(package_files)) as p_bar:
            for (i, filename) in enumerate(sorted(package_files)):
                cmdline = self.py2rpm_start_cmdline() + ["--", filename]
                build_filename = "py2rpm-%s.out" % sh.basename(filename)
                out_filename = sh.joinpths(self.log_dir, build_filename)
                sh.execute_save_output(cmdline, out_filename=out_filename,
                                       quiet=True)
                p_bar.update(i + 1)

    def _build_openstack(self):
        if not self.package_dirs:
            LOG.warn("No RPM packages of OpenStack installs to build")
            return
        component_names = [self._get_component_name(d)
                           for d in self.package_dirs]
        utils.log_iterable(sorted(component_names), logger=LOG,
                           header=("Building %s OpenStack RPM"
                                   " packages") % (len(self.package_dirs)))
        with utils.progress_bar(name='Building',
                                max_am=len(self.package_dirs)) as p_bar:
            for (i, pkg_dir) in enumerate(sorted(self.package_dirs)):
                component_name = self._get_component_name(pkg_dir)
                cmdline = self.py2rpm_start_cmdline() + ["--", pkg_dir]
                out_filename = sh.joinpths(self.log_dir,
                                           "py2rpm.%s.out" % (component_name))
                sh.execute_save_output(cmdline, out_filename=out_filename,
                                       quiet=True)
                p_bar.update(i + 1)

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
            sh.execute(cmdline)
        LOG.info("Writing %s to %s", self.REPO_FN, self.anvil_repo_filename)
        (_fn, content) = utils.load_template('packaging', self.REPO_FN)
        params = {"baseurl_bin": "file://%s" % self.deps_repo_dir,
                  "baseurl_src": "file://%s" % self.deps_src_repo_dir}
        sh.write_file(self.anvil_repo_filename,
                      utils.expand_template(content, params),
                      tracewriter=self.tracewriter)

    def _convert_names_python2rpm(self, python_names):
        if not self.python_names:
            return []

        cmdline = self.py2rpm_start_cmdline() + ["--convert"] + python_names
        rpm_names = []
        for name in sh.execute(cmdline)[0].splitlines():
            # name is "Requires: rpm-name"
            try:
                rpm_names.append(name.split(":")[1].strip())
            except IndexError:
                pass
        return rpm_names

    def install(self):
        super(YumDependencyHandler, self).install()
        repo_filename = sh.joinpths(self.YUM_REPO_DIR, self.REPO_FN)

        # Ensure we copy the local repo file name to the main repo so that
        # yum will find it when installing packages.
        sh.write_file(repo_filename, sh.load_file(self.anvil_repo_filename),
                      tracewriter=self.tracewriter)

        # Erase it if its been previously installed.
        cmdline = []
        if self.helper.is_installed(self.OPENSTACK_DEPS_PACKAGE_NAME):
            cmdline.append(self.OPENSTACK_DEPS_PACKAGE_NAME)
        for p in self.nopackages:
            if self.helper.is_installed(p):
                cmdline.append(p)

        if cmdline:
            cmdline = ["yum", "erase", "-y"] + cmdline
            sh.execute(cmdline, stdout_fh=sys.stdout, stderr_fh=sys.stderr)

        cmdline = ["yum", "clean", "all"]
        sh.execute(cmdline)

        cmdline = ["yum", "install", "-y", self.OPENSTACK_DEPS_PACKAGE_NAME]
        sh.execute(cmdline, stdout_fh=sys.stdout, stderr_fh=sys.stderr)

        rpm_names = self._convert_names_python2rpm(self.python_names)
        if rpm_names:
            cmdline = ["yum", "install", "-y"] + rpm_names
            sh.execute(cmdline, stdout_fh=sys.stdout, stderr_fh=sys.stderr)

    def uninstall(self):
        super(YumDependencyHandler, self).uninstall()
        if self.tracereader.exists():
            for f in self.tracereader.files_touched():
                sh.unlink(f)
            for d in self.tracereader.dirs_made():
                sh.deldir(d)
            sh.unlink(self.tracereader.filename())
            self.tracereader = None

        # Don't take out packages that anvil requires to run...
        no_remove = env.get_key('REQUIRED_PACKAGES', '').split()
        no_remove = sorted(set(no_remove))
        rpm_names = []
        for name in self._convert_names_python2rpm(self.python_names):
            if self.helper.is_installed(name) and name not in no_remove:
                rpm_names.append(name)

        if rpm_names:
            cmdline = ["yum", "remove", "--remove-leaves", "-y"]
            for p in no_remove:
                cmdline.append("--exclude=%s" % (p))
            cmdline.extend(rpm_names)
            sh.execute(cmdline, stdout_fh=sys.stdout, stderr_fh=sys.stderr)
