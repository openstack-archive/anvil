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
import sys

import pkg_resources
import rpm

from anvil import log as logging
from anvil.packaging import base
from anvil.packaging.helpers import pip_helper
from anvil.packaging.helpers import yum_helper
from anvil import settings
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
    YUM_REPO_DIR = "/etc/yum.repos.d"
    rpmbuild_executable = sh.which("rpmbuild")

    def __init__(self, distro, root_dir, instances, opts=None):
        super(YumDependencyHandler, self).__init__(distro, root_dir, instances, opts)
        self.rpmbuild_dir = sh.joinpths(self.deps_dir, "rpmbuild")
        # Track what file we create so they can be cleaned up on uninstall.
        trace_fn = tr.trace_filename(root_dir, 'deps')
        self.tracewriter = tr.TraceWriter(trace_fn, break_if_there=False)
        self.tracereader = tr.TraceReader(trace_fn)
        self.helper = yum_helper.Helper()
        self.rpm_sources_dir = sh.joinpths(self.rpmbuild_dir, "SOURCES")
        self.anvil_repo_dir = sh.joinpths(self.root_dir, "repo")

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

    def _package_parameters(self, instance):
        params = {}
        params["release"] = instance.get_option("release", default_value="1")
        if '-' in params["release"]:
            # NOTE(imelnikov): "-" is prohibited in RPM releases
            raise ValueError("Malformed package release: %r" % params["release"])

        version_suffix = instance.get_option("version_suffix", default_value="")
        if version_suffix and not version_suffix.startswith('.'):
            version_suffix = '.' + version_suffix
        params['version_suffix'] = version_suffix
        tests_package = instance.get_option('tests_package', default_value={})

        params["no_tests"] = 0 if tests_package.get('enabled', True) else 1
        test_exclusions = set(instance.get_option("exclude_tests",
                                                  default_value=()))
        test_exclusions.update(tests_package.get("exclude_tests", ()))
        params["exclude_tests"] = sorted(test_exclusions)
        params["exclude_from_test_env"] = ['./bin', './build*']
        params["exclude_from_test_env"].extend(
                tests_package.get("exclude_from_env", ()))
        return params

    def package_instance(self, instance):
        # clear before...
        sh.deldir(self.rpmbuild_dir)
        for dirname in (sh.joinpths(self.rpmbuild_dir, "SPECS"),
                        sh.joinpths(self.rpmbuild_dir, "SOURCES")):
            sh.mkdir(dirname, recurse=True)
        if instance.name == "general":
            self._build_dependencies()
            self._move_srpms("anvil-deps")
        else:
            app_dir = instance.get_option("app_dir")
            if sh.isdir(app_dir):
                params = self._package_parameters(instance)
                self._build_openstack_package(app_dir, params,
                                              instance.list_patches("package"))
                self._move_srpms("anvil")
        # ...and after
        sh.deldir(self.rpmbuild_dir)

    def _move_rpm_files(self, source_dir, target_dir):
        if not sh.isdir(source_dir):
            return
        if not sh.isdir(target_dir):
            sh.mkdirslist(target_dir, tracewriter=self.tracewriter)
        for filename in sh.listdir(source_dir, recursive=True, files_only=True):
            if not filename.lower().endswith(".rpm"):
                continue
            sh.move(filename, target_dir, force=True)

    def build_binary(self):
        build_requires = self.requirements["build-requires"]
        if build_requires:
            build_requires = list(build_requires)
            self.helper.transaction(install_pkgs=build_requires,
                                    tracewriter=self.tracewriter)

        ts = rpm.TransactionSet()
        for repo_name in "anvil-deps", "anvil":
            repo_dir = sh.joinpths(self.anvil_repo_dir, repo_name)
            for srpm_filename in sh.listdir(
                    sh.joinpths(self.anvil_repo_dir, "%s-sources" % repo_name),
                    files_only=True):
                with open(srpm_filename) as fd:
                    hdr = ts.hdrFromFdno(fd)
                bin_rpm_filename = "%s-%s-%s.%s.rpm" % (
                    hdr[rpm.RPMTAG_NAME],
                    hdr[rpm.RPMTAG_VERSION],
                    hdr[rpm.RPMTAG_RELEASE],
                    hdr[rpm.RPMTAG_ARCH])
                if sh.isfile(sh.joinpths(repo_dir, bin_rpm_filename)):
                    LOG.info("Found RPM package %s", bin_rpm_filename)
                    continue
                # clear before...
                sh.deldir(self.rpmbuild_dir)
                base_filename = sh.basename(srpm_filename)
                LOG.info("Building RPM package from %s", base_filename)
                self.helper.builddep(srpm_filename, self.tracewriter)
                cmdline = [
                    "rpmbuild",
                    "--define", "_topdir %s" % self.rpmbuild_dir,
                    "--rebuild",
                    srpm_filename]
                if self.opts.get("usr_only", False):
                    cmdline.extend(["--define", "usr_only 1"])
                sh.execute_save_output(
                    cmdline,
                    out_filename=sh.joinpths(
                            self.log_dir, "rpmbuild-%s.out" % base_filename))
                self._move_rpm_files(sh.joinpths(self.rpmbuild_dir, "RPMS"), repo_dir)
                # ...and after
                sh.deldir(self.rpmbuild_dir)
            self._create_repo(repo_name)

    def _move_srpms(self, repo_name):
        src_repo_dir = sh.joinpths(self.anvil_repo_dir, "%s-sources" % repo_name)
        self._move_rpm_files(sh.joinpths(self.rpmbuild_dir, "SRPMS"), src_repo_dir)

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
        # install *.repo file so that anvil deps will be available
        # when building OpenStack
        sh.copy(repo_filename, "%s/%s.repo" % (self.YUM_REPO_DIR, repo_name))

    def filter_download_requires(self):
        yum_map = {}
        for pkg in self.helper.get_available():
            for provides in pkg['provides']:
                yum_map.setdefault(provides[0], set()).add(
                    (pkg['version'], pkg['repo']))

        pips_to_download = []
        req_to_install = [pkg_resources.Requirement.parse(pkg)
                          for pkg in self.pips_to_install]
        requested_names = [req.key for req in req_to_install]
        rpm_to_install = self._convert_names_python2rpm(requested_names)

        satisfied_list = []
        for (req, rpm_name) in zip(req_to_install, rpm_to_install):
            yum_versions = yum_map.get(rpm_name, [])
            satisfied = False
            for (version, repo) in yum_versions:
                if version in req:
                    satisfied = True
                    satisfied_list.append((req, rpm_name, version, repo))
                    break
            if not satisfied:
                pips_to_download.append(str(req))

        if satisfied_list:
            # Organize by repo
            repos = collections.defaultdict(list)
            for (req, rpm_name, version, repo) in satisfied_list:
                repos[repo].append("%s as %s-%s" % (req, rpm_name, version))
            for r in sorted(repos.keys()):
                header = ("%s Python packages are already available "
                          "as RPMs from repository %s")
                utils.log_iterable(sorted(repos[r]), logger=LOG,
                                   header=header % (len(repos[r]), r))
        return pips_to_download

    @staticmethod
    def _get_component_name(pkg_dir):
        return sh.basename(sh.dirname(pkg_dir))

    def _build_dependencies(self):
        package_files = self.download_dependencies()
        if not package_files:
            LOG.info("No RPM packages of OpenStack dependencies to build")
            return
        for filename in package_files:
            LOG.info("Building SRPM package from %s", filename)
            scripts_dir = sh.abspth(sh.joinpths(
                settings.TEMPLATE_DIR, "packaging/scripts"))
            cmdline = self.py2rpm_start_cmdline() + [
                "--scripts-dir", scripts_dir, "--source-only", "--", filename]
            sh.execute(cmdline)

    @staticmethod
    def _python_setup_py_get(pkg_dir, field):
        """
        :param field: e.g., "name" or "version"
        """
        cmdline = [sys.executable, "setup.py", "--%s" % field]
        value = sh.execute(cmdline, cwd=pkg_dir)[0].splitlines()[-1].strip()
        if not value:
            LOG.error("Cannot determine %s for %s", field, pkg_dir)
        return value

    def _parse_requires_file(self, requires_filename):
        result = []
        if sh.isfile(requires_filename):
            requires_python = pip_helper.parse_requirements(
                open(requires_filename, "r").read())
            if requires_python:
                result = self._convert_names_python2rpm(
                    [r.key for r in requires_python if r.key not in (
                        'setuptools', 'setuptools-git', 'sphinx', 'docutils')])
        return result

    def _write_spec_file(self, pkg_dir, rpm_name, template_name, params):
        if not params.setdefault("requires", []):
            params["requires"] = self._parse_requires_file(
                sh.joinpths(pkg_dir, "tools", "pip-requires"))
        if not params.setdefault("test_requires", []):
            params['test_requires'] = self._parse_requires_file(
                sh.joinpths(pkg_dir, "tools", "test-requires"))

        params["epoch"] = self.OPENSTACK_EPOCH
        params["part_fn"] = lambda filename: sh.joinpths(
                settings.TEMPLATE_DIR,
                self.SPEC_TEMPLATE_DIR,
                filename)

        content = utils.load_template(self.SPEC_TEMPLATE_DIR, template_name)[1]
        spec_filename = sh.joinpths(
            self.rpmbuild_dir, "SPECS", "%s.spec" % rpm_name)
        sh.write_file(spec_filename, utils.expand_template(content, params))
        return spec_filename

    def _copy_startup_scripts(self, spec_filename):
        common_init_content = utils.load_template(
            "packaging", "common.init")[1]
        for src in rpm.spec(spec_filename).sources:
            script = sh.basename(src[0])
            if not (script.endswith(".init")):
                continue
            target_filename = sh.joinpths(self.rpm_sources_dir, script)
            if sh.isfile(target_filename):
                continue
            bin_name = utils.strip_prefix_suffix(
                script, "openstack-", ".init")
            if bin_name == "quantum-server":
                daemon_args = ("'--config-file=/etc/quantum/plugin.ini"
                               " --config-file=/etc/quantum/quantum.conf'")
            elif bin_name == "quantum-l3-agent":
                daemon_args = ("'--config-file=/etc/quantum/l3_agent.ini"
                               " --config-file=/etc/quantum/quantum.conf'")
            elif bin_name == "quantum-dhcp-agent":
                daemon_args = ("'--config-file=/etc/quantum/dhcp_agent.ini"
                               " --config-file=/etc/quantum/quantum.conf'")
            else:
                daemon_args = ""
            params = {
                "bin": bin_name,
                "package": bin_name.split("-", 1)[0],
                "daemon_args": daemon_args,
            }
            sh.write_file(
                target_filename,
                utils.expand_template(common_init_content, params))

    def _copy_sources(self, pkg_dir):
        component_name = self._get_component_name(pkg_dir)
        other_sources_dir = sh.joinpths(
            settings.TEMPLATE_DIR, "packaging/sources", component_name)
        if sh.isdir(other_sources_dir):
            for filename in sh.listdir(other_sources_dir, files_only=True):
                sh.copy(filename, self.rpm_sources_dir)

    def _copy_patches(self, patches):
        for filename in patches:
            sh.copy(filename, self.rpm_sources_dir)

    def _build_from_spec(self, pkg_dir, spec_filename, patches=()):
        if sh.isfile(sh.joinpths(pkg_dir, "setup.py")):
            self._write_python_tarball(pkg_dir)
        else:
            self._write_git_tarball(pkg_dir, spec_filename)
        self._copy_sources(pkg_dir)
        self._copy_patches(patches)
        self._copy_startup_scripts(spec_filename)
        cmdline = [
            self.rpmbuild_executable,
            "-bs",
            "--define", "_topdir %s" % self.rpmbuild_dir,
            spec_filename,
        ]
        sh.execute(cmdline)

    def _write_git_tarball(self, pkg_dir, spec_filename):
        cmdline = [
            "rpm",
            "-q",
            "--specfile", spec_filename,
            "--qf", "%{NAME}-%{VERSION}\n"
        ]
        tar_base = sh.execute(cmdline, cwd=pkg_dir)[0].splitlines()[0].strip()
        # git 1.7.1 from RHEL doesn't understand --format=tar.gz
        output_filename = sh.joinpths(
            self.rpm_sources_dir, "%s.tar" % tar_base)
        cmdline = [
            "git",
            "archive",
            "--format=tar",
            "--prefix=%s/" % tar_base,
            "--output=%s" % output_filename,
            "HEAD",
        ]
        sh.execute(cmdline, cwd=pkg_dir)
        cmdline = ["gzip", output_filename]
        sh.execute(cmdline)

    def _write_python_tarball(self, pkg_dir):
        cmdline = [
            sys.executable,
            "setup.py",
            "sdist",
            "--formats", "gztar",
            "--dist-dir", self.rpm_sources_dir,
        ]
        sh.execute(cmdline, cwd=pkg_dir)

    def _build_openstack_package(self, pkg_dir, params=None, patches=()):
        component_name = self._get_component_name(pkg_dir)
        params = params or {}
        params['patches'] = [sh.basename(fn) for fn in patches]

        rpm_name = None
        template_name = None
        if sh.isfile(sh.joinpths(pkg_dir, "setup.py")):
            name = self._python_setup_py_get(pkg_dir, "name")
            params["version"] = self._python_setup_py_get(pkg_dir, "version")
            if component_name.endswith("client"):
                clientname = utils.strip_prefix_suffix(
                    name, "python-", "client")
                if not clientname:
                    LOG.error("Bad client package name %s", name)
                    return
                params["clientname"] = clientname
                params["apiname"] = self.API_NAMES.get(
                    clientname, clientname.title())
                rpm_name = name
                template_name = "python-commonclient.spec"
            elif component_name in self.SERVER_NAMES:
                rpm_name = "openstack-%s" % name
            elif component_name == "horizon":
                rpm_name = "python-django-horizon"
        else:
            rpm_name = component_name
            template_name = "%s.spec" % rpm_name
            spec_filename = sh.joinpths(
                settings.TEMPLATE_DIR,
                self.SPEC_TEMPLATE_DIR,
                template_name)
            if not sh.isfile(spec_filename):
                rpm_name = None
        if rpm_name:
            template_name = template_name or "%s.spec" % rpm_name
            spec_filename = self._write_spec_file(
                pkg_dir, rpm_name, template_name, params)
            self._build_from_spec(pkg_dir, spec_filename, patches)
        else:
            cmdline = self.py2rpm_start_cmdline()
            if not params["no_tests"]:
                cmdline.append("--with-tests")
            cmdline.extend([
                "--source-only",
                "--release", params["release"],
                "--", pkg_dir])
            sh.execute(cmdline, cwd=pkg_dir)

    def _convert_names_python2rpm(self, python_names):
        if not python_names:
            return []

        cmdline = self.py2rpm_start_cmdline() + ["--convert"] + python_names
        rpm_names = []
        for name in sh.execute(cmdline)[0].splitlines():
            # name is "Requires: rpm-name"
            try:
                rpm_names.append(name.split(":", 1)[1].strip())
            except IndexError:
                pass
        return rpm_names

    def _all_rpm_names(self):
        req_names = [pkg_resources.Requirement.parse(pkg).key
                     for pkg in open(self.gathered_requires_filename)]
        rpm_names = set(self._convert_names_python2rpm(req_names))
        rpm_names |= self.requirements["requires"]
        for inst in self.instances:
            rpm_names |= inst.package_names()
        return list(rpm_names)

    def install(self):
        super(YumDependencyHandler, self).install()
        self.helper.clean()  # repositories might have been changed
        # Erase conflicting packages

        remove_pkgs = []
        for p in self.requirements["conflicts"]:
            if self.helper.is_installed(p):
                remove_pkgs.append(p)

        self.helper.transaction(install_pkgs=self._all_rpm_names(),
                                remove_pkgs=remove_pkgs,
                                tracewriter=self.tracewriter)

    def uninstall(self):
        super(YumDependencyHandler, self).uninstall()
        if self.tracereader.exists():
            for f in self.tracereader.files_touched():
                sh.unlink(f)
            for d in self.tracereader.dirs_made():
                sh.deldir(d)
            remove_pkgs = self.tracereader.packages_installed()
            self.helper.transaction(remove_pkgs=remove_pkgs)
            sh.unlink(self.tracereader.filename())
            self.tracereader = None
