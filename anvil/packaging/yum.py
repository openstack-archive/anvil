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

import pkg_resources

from anvil import log as logging
from anvil.packaging import base
from anvil.packaging.helpers import yum_helper
from anvil import settings
from anvil import shell as sh
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
    SPEC_TEMPLATE_DIR = "packaging/specs"
    API_NAMES = {
        "nova": "Compute",
        "glance": "Image",
        "keystone": "Identity",
        "cinder": "Volume",
        "quantum": "Networking",
    }
    SERVER_NAMES = ["nova", "glance", "keystone", "quantum", "cinder"]
    py2rpm_executable = sh.which("py2rpm", ["tools/"])
    rpmbuild_executable = sh.which("rpmbuild")

    def __init__(self, distro, root_dir, instances):
        super(YumDependencyHandler, self).__init__(distro, root_dir, instances)
        self.rpmbuild_dir = sh.joinpths(self.deps_dir, "rpmbuild")
        self.rpm_sources_dir = sh.joinpths(self.rpmbuild_dir, "SOURCES")
        self.anvil_repo_dir = sh.joinpths(self.deps_dir, "repo")

    def _epoch_list(self):
        return [
            "--epoch-list",
        ] + ["%s==%s" % (name, self.OPENSTACK_EPOCH) for name in self.python_names]

    def package_instance(self, instance):
        for dirname in (sh.joinpths(self.rpmbuild_dir, "SPECS"),
                        sh.joinpths(self.rpmbuild_dir, "SOURCES")):
            sh.deldir(dirname)
            sh.mkdir(dirname, recurse=True)
        if instance.name == "general":
            self._build_dependencies()
            self._move_rpms("anvil-deps")
            self._create_repo("anvil-deps")
            self._write_all_deps_package()
            self._move_rpms("anvil")
            return
        app_dir = instance.get_option("app_dir")
        if sh.isdir(app_dir):
            self._build_openstack_package(app_dir)
            self._move_rpms("anvil")

    def package_finish(self):
        self._create_repo("anvil")

    def _move_rpms(self, repo_name):
        repo_dir = sh.joinpths(self.anvil_repo_dir, repo_name)
        src_repo_dir = "%s-sources" % repo_dir
        sh.mkdir(repo_dir, recurse=True)
        sh.mkdir(src_repo_dir, recurse=True)
        for filename in sh.listdir(sh.joinpths(self.rpmbuild_dir, "RPMS"),
                                   recursive=True, files_only=True):
            sh.move(filename, repo_dir, force=True)
        for filename in sh.listdir(sh.joinpths(self.rpmbuild_dir, "SRPMS"),
                                   recursive=True, files_only=True):
            sh.move(filename, src_repo_dir, force=True)
        return repo_dir

    def _create_repo(self, repo_name):
        repo_dir = sh.joinpths(self.anvil_repo_dir, repo_name)
        src_repo_dir = "%s-sources" % repo_dir
        for a_dir in repo_dir, src_repo_dir:
            cmdline = ["createrepo", a_dir]
            LOG.info("Creating repo at %s" % a_dir)
            sh.execute(cmdline)
        repo_filename = sh.joinpths(self.anvil_repo_dir, "%s.repo" % repo_name)
        LOG.info("Writing %s" % repo_filename)
        (_fn, content) = utils.load_template("packaging", "common.repo")
        params = {
            "repo_name": repo_name,
            "baseurl_bin": "file://%s" % repo_dir,
            "baseurl_src": "file://%s" % src_repo_dir
        }
        sh.write_file(
            repo_filename, utils.expand_template(content, params))

    def filter_download_requires(self):
        yum_map = {}
        for pkg in yum_helper.Helper().get_available():
            for provides in pkg.provides:
                yum_map.setdefault(provides[0], set()).add(
                    (pkg.version, pkg.repo.id))

        nopips = [pkg_resources.Requirement.parse(name).key
                  for name in self.python_names]
        pips_to_download = []
        req_to_install = [pkg_resources.Requirement.parse(pkg)
                          for pkg in self.pips_to_install]
        req_to_install = [
            req for req in req_to_install if req.key not in nopips]
        rpm_to_install = self._convert_names_python2rpm(
            [req.key for req in req_to_install])
        satisfied_list = []
        for req, rpm_name in zip(req_to_install, rpm_to_install):
            yum_versions = yum_map.get(rpm_name, [])
            satisfied = False
            for (version, repo_id) in yum_versions:
                if version in req:
                    satisfied = True
                    satisfied_list.append(
                        "%s as %s-%s from %s" %
                        (req, rpm_name, version, repo_id))
                    break
            if not satisfied:
                pips_to_download.append(str(req))
        if satisfied_list:
            utils.log_iterable(
                sorted(satisfied_list), logger=LOG,
                header="These Python packages are already available as RPMs")
        return pips_to_download

    def _write_all_deps_package(self):
        spec_filename = sh.joinpths(
            self.rpmbuild_dir,
            "SPECS",
            "%s.spec" % self.OPENSTACK_DEPS_PACKAGE_NAME)

        today = datetime.date.today()
        spec_content = """Name: %s
Version: %s.%s.%s
Release: 0
License: Apache 2.0
Summary: OpenStack dependencies
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
        sh.write_file(spec_filename, spec_content)
        cmdline = [
            "rpmbuild", "-ba",
            "--define", "_topdir %s" % self.rpmbuild_dir,
            spec_filename,
        ]
        LOG.info("Building %s RPM" % self.OPENSTACK_DEPS_PACKAGE_NAME)
        sh.execute(cmdline)

    def _build_dependencies(self):
        #        package_files = self.download_dependencies()
        package_files = sh.listdir(self.download_dir, files_only=True)
        if not package_files:
            LOG.info("No RPM packages of OpenStack dependencies to build")
            return
        for filename in package_files:
            LOG.info("Building RPM package from %s", filename)
            cmdline = [
                self.py2rpm_executable,
                "--rpm-base",
                self.rpmbuild_dir,
            ] + self._epoch_list() + ["--", filename]
            sh.execute_save_output(
                cmdline,
                out_filename=sh.joinpths(
                    self.log_dir, "py2rpm-%s.out" % sh.basename(filename)))

    @staticmethod
    def _get_component_name(pkg_dir):
        return sh.basename(sh.dirname(pkg_dir))

    @staticmethod
    def _python_get_name_version(pkg_dir):
        cmdline = [sys.executable, "setup.py", "--name", "--version"]
        name_version = sh.execute(cmdline, cwd=pkg_dir)[0].splitlines()
        if len(name_version) < 2:
            LOG.error("Cannot determine name and version for %s", pkg_dir)
            return
        return (name_version[-2].strip(), name_version[-1].strip())

    def _write_spec_file(self, rpm_name, version, template_name, params):
        # TODO(aababilov): write Requires
        params["version"] = version
        params["epoch"] = self.OPENSTACK_EPOCH
        content = utils.load_template(self.SPEC_TEMPLATE_DIR, template_name)[1]
        spec_filename = sh.joinpths(
            self.rpmbuild_dir, "SPECS", "%s.spec" % rpm_name)
        sh.write_file(spec_filename, utils.expand_template(content, params))
        return spec_filename

    def _build_openstack_package_client(self, pkg_dir):
        name, version = self._python_get_name_version(pkg_dir)
        clientname = utils.strip_prefix_suffix(name, "python-", "client")
        if not clientname:
            LOG.error("Bad client package name %s", name)
            return
        params = {
            "clientname": clientname,
            "apiname": self.API_NAMES.get(clientname, clientname.title()),
            "requires": []
        }
        spec_filename = self._write_spec_file(
            name, version, "python-commonclient.spec", params)
        self._build_from_spec(pkg_dir, spec_filename)

    def _build_openstack_package_server(self, pkg_dir):
        name, version = self._python_get_name_version(pkg_dir)
        spec_filename = "openstack-%s.spec" % name
        spec_content = utils.load_template(self.SPEC_TEMPLATE_DIR, spec_filename)[1]
        common_init_content = utils.load_template(
            "packaging/init.d", "common.init")[1]

        init_params = {
            "package": name,
            "config": "%s.conf" % name,
        }
        for line in spec_content.splitlines():
            line = line.strip()
            if line.startswith("Source") and line.endswith(".init"):
                try:
                    script = line.split(None, 1)[1]
                except IndexError:
                    pass
                else:
                    init_params["bin"] = utils.strip_prefix_suffix(
                        script, "openstack-", ".init")
                    sh.write_file(
                        sh.joinpths(self.rpm_sources_dir, script),
                        utils.expand_template(
                            common_init_content, init_params))

        params = {
            "requires": []
        }
        spec_filename = self._write_spec_file(
            "openstack-%s" % name, version, spec_filename, params)
        self._build_from_spec(pkg_dir, spec_filename)

    def _build_from_spec(self, pkg_dir, spec_filename):
        if sh.isfile(sh.joinpths(pkg_dir, "setup.py")):
            self._write_python_tarball(pkg_dir)
        else:
            self._write_git_tarball(pkg_dir, spec_filename)
        component_name = self._get_component_name(pkg_dir)
        other_sources_dir = sh.joinpths(
            settings.TEMPLATE_DIR, "packaging/sources", component_name)
        if sh.isdir(other_sources_dir):
            for filename in sh.listdir(other_sources_dir, files_only=True):
                sh.copy(filename, self.rpm_sources_dir)
        cmdline = [
            self.rpmbuild_executable,
        # FIXME(aababilov): -ba
            "-ba",
            "--define", "_topdir %s" % self.rpmbuild_dir,
            spec_filename,
        ]
        sh.execute_save_output(
            cmdline, sh.joinpths(self.log_dir, sh.basename(spec_filename)))

    def _write_git_tarball(self, pkg_dir, spec_filename):
        cmdline = [
            "rpm",
            "-q",
            "--specfile", spec_filename,
            "--qf", "%{NAME}-%{VERSION}\n"
        ]
        tar_base = sh.execute(cmdline, cwd=pkg_dir)[0].splitlines()[0].strip()
        output_filename = sh.joinpths(
            self.rpm_sources_dir, "%s.tar.gz" % tar_base)
        cmdline = [
            "git",
            "archive",
            "--format=tar.gz",
            "--prefix=%s/" % tar_base,
            "--output=%s" % output_filename,
            "HEAD",
        ]
        sh.execute(cmdline, cwd=pkg_dir)

    def _write_python_tarball(self, pkg_dir):
        cmdline = [
            sys.executable,
            "setup.py",
            "sdist",
            "--formats", "gztar",
            "--dist-dir", self.rpm_sources_dir,
        ]
        sh.execute(cmdline, cwd=pkg_dir)

    def _build_openstack_package(self, pkg_dir):
        component_name = self._get_component_name(pkg_dir)
        if component_name in self.SERVER_NAMES:
            self._build_openstack_package_server(pkg_dir)
            return
        if component_name.endswith("client"):
            self._build_openstack_package_client(pkg_dir)
            return
        spec_filename = sh.joinpths(
            settings.TEMPLATE_DIR,
            self.SPEC_TEMPLATE_DIR,
            "%s.spec" % component_name)
        if sh.isfile(spec_filename):
            spec_filename = self._write_spec_file(
                component_name, 1, "%s.spec" % component_name, {})
            self._build_from_spec(pkg_dir, spec_filename)
            return
        cmdline = [
            self.py2rpm_executable,
            "--rpm-base",
            self.rpmbuild_dir,
            pkg_dir
        ] + self._epoch_list()
        sh.execute_save_output(
            cmdline, cwd=pkg_dir,
            out_filename=sh.joinpths(self.log_dir, component_name))

    def _convert_names_python2rpm(self, python_names):
        if not self.python_names:
            return []

        cmdline = [self.py2rpm_executable, "--convert"] + python_names
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
        helper = yum_helper.Helper()

        # Ensure we copy the local repo file name to the main repo so that
        # yum will find it when installing packages.
        for repo_name in "anvil", "anvil-deps":
            repo_filename = sh.joinpths(
                self.anvil_repo_dir, "%s.repo" % repo_name)
            if sh.isfile(repo_filename):
                sh.copy(repo_filename, "/etc/yum.repos.d/")

        cmdline = []
        if helper.is_installed(self.OPENSTACK_DEPS_PACKAGE_NAME):
            cmdline = [self.OPENSTACK_DEPS_PACKAGE_NAME]

        for p in self.nopackages:
            if helper.is_installed(p):
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
        helper = yum_helper.Helper()
        rpm_names = []
        for name in self._convert_names_python2rpm(self.python_names):
            if helper.is_installed(name):
                rpm_names.append(name)

        if rpm_names:
            cmdline = ["yum", "remove", "--remove-leaves", "-y"] + rpm_names
            sh.execute(cmdline, stdout_fh=sys.stdout, stderr_fh=sys.stderr)
