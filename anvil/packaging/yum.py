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
import contextlib
import json
import pkg_resources
import sys
import tarfile

from anvil import colorizer
from anvil import exceptions as excp
from anvil import log as logging
from anvil.packaging import base
from anvil.packaging.helpers import pip_helper
from anvil.packaging.helpers import yum_helper
from anvil import settings
from anvil import shell as sh
from anvil import utils

LOG = logging.getLogger(__name__)

# Certain versions of pbr seem to miss these files, which causes the rpmbuild
# phases to not complete correctly. Ensure that we don't miss them.
ENSURE_NOT_MISSING = [
    'doc',  # Without this one our rpm doc build won't work
    'README.rst',  # Without this one pbr won't work (thus killing setup.py)
    'babel.cfg',
    'HACKING',
    'AUTHORS',
    'ChangeLog',
    'CONTRIBUTING.rst',
    'LICENSE',
]


class YumInstallHelper(base.InstallHelper):
    def pre_install(self, pkg, params=None):
        """pre-install is handled in openstack-deps %pre script."""
        pass

    def post_install(self, pkg, params=None):
        """post-install is handled in openstack-deps %post script."""
        pass


class YumDependencyHandler(base.DependencyHandler):
    OPENSTACK_EPOCH = 2
    SPEC_TEMPLATE_DIR = "packaging/specs"
    # TODO(harlowja): get rid of these static lists/mappings from code and move
    # them to configuration (or elsewhere).
    API_NAMES = {
        "nova": "Compute",
        "glance": "Image",
        "keystone": "Identity",
        "cinder": "Volume",
        "neutron": "Networking",
    }
    SERVER_NAMES = ["nova", "glance", "keystone", "neutron", "cinder", "trove"]
    TRANSLATION_NAMES = {
        'horizon': "python-django-horizon",
    }
    YUM_REPO_DIR = "/etc/yum.repos.d/"
    SRC_REPOS = {
        'anvil': 'anvil-source',
        "anvil-deps": "anvil-deps-source",
    }
    REPOS = ["anvil-deps", "anvil"]
    JOBS = 2

    def __init__(self, distro, root_dir, instances, opts=None):
        super(YumDependencyHandler, self).__init__(distro, root_dir, instances, opts)
        # Various paths we will use while operating
        self.rpmbuild_dir = sh.joinpths(self.deps_dir, "rpmbuild")
        self.deps_repo_dir = sh.joinpths(self.deps_dir, "openstack-deps")
        self.deps_src_repo_dir = sh.joinpths(self.deps_dir, "openstack-deps-sources")
        self.rpm_sources_dir = sh.joinpths(self.rpmbuild_dir, "SOURCES")
        self.anvil_repo_dir = sh.joinpths(self.root_dir, "repo")
        # Executables we require to operate
        self.py2rpm_executable = sh.which("py2rpm", ["tools/"])
        self.rpmbuild_executable = sh.which("rpmbuild")
        self.specprint_executable = sh.which('specprint', ["tools/"])
        self.yumfind_executable = sh.which("yumfind", ["tools/"])
        # We inspect yum for packages, this helper allows us to do this.
        self.helper = yum_helper.Helper(self.log_dir)
        # See if we are requested to run at a higher make parallelism level
        self._jobs = self.JOBS
        if 'jobs' in self.opts:
            try:
                self._jobs = int(self.opts.get('jobs', self.JOBS))
                if self._jobs <= 0:
                    self._jobs = self.JOBS
            except (TypeError, ValueError):
                pass

    def _py2rpm_start_cmdline(self):
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
        package_map = self.distro.get_dependency_config("package_map")
        if package_map:
            cmdline += [
                "--package-map",
            ] + ["%s==%s" % (key, value)
                 for key, value in package_map.iteritems()]
        arch_dependent = self.distro.get_dependency_config("arch_dependent")
        if arch_dependent:
            cmdline += [
                "--arch-dependent",
            ] + list(arch_dependent)
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
        return params

    def _create_rpmbuild_subdirs(self):
        for dirname in (sh.joinpths(self.rpmbuild_dir, "SPECS"),
                        sh.joinpths(self.rpmbuild_dir, "SOURCES")):
            sh.mkdirslist(dirname, tracewriter=self.tracewriter)

    def package_instance(self, instance):
        with sh.remove_before_after(self.rpmbuild_dir):
            self._create_rpmbuild_subdirs()
            if instance.name in ["general"]:
                self._build_dependencies()
                self._move_srpms("anvil-deps")
            else:
                # Meta packages don't get built.
                app_dir = instance.get_option("app_dir")
                if sh.isdir(app_dir):
                    self._build_openstack_package(instance)
                    self._move_srpms("anvil")

    def _move_rpm_files(self, source_dir, target_dir):
        # NOTE(imelnikov): we should create target_dir even if we have
        #  nothing to move, because later we rely on its existence
        if not sh.isdir(target_dir):
            sh.mkdirslist(target_dir, tracewriter=self.tracewriter)
        if not sh.isdir(source_dir):
            return
        for filename in sh.listdir(source_dir, recursive=True, files_only=True):
            if not filename.lower().endswith(".rpm"):
                continue
            sh.move(filename, target_dir, force=True)

    def post_bootstrap(self):
        bs_rpmbuild_dir = sh.joinpths('.bootstrap', 'rpmbuild')
        if sh.isdir(bs_rpmbuild_dir):
            LOG.info("Moving RPMS build on bootstrap to deps repo")
            self._move_srpms("anvil-deps", bs_rpmbuild_dir)
            self._move_rpm_files(bs_rpmbuild_dir,
                                 sh.joinpths(self.anvil_repo_dir, 'anvil-deps'))
            sh.deldir(bs_rpmbuild_dir)

    def build_binary(self):
        def is_src_rpm(path):
            if not path:
                return False
            if not sh.isfile(path):
                return False
            if not path.lower().endswith('.src.rpm'):
                return False
            return True

        def list_src_rpms(path):
            path_files = []
            if sh.isdir(path):
                path_files = sh.listdir(path, filter_func=is_src_rpm)
            return sorted(path_files)

        build_requirements = self.requirements.get("build-requires")
        if build_requirements:
            utils.log_iterable(build_requirements,
                               header="Installing build requirements",
                               logger=LOG)
            self.helper.transaction(install_pkgs=build_requirements,
                                    tracewriter=self.tracewriter)

        for repo_name in self.REPOS:
            src_repo_dir = sh.joinpths(self.anvil_repo_dir, self.SRC_REPOS[repo_name])
            src_repo_files = list_src_rpms(src_repo_dir)
            if not src_repo_files:
                continue
            utils.log_iterable(src_repo_files,
                               header=('Building %s RPM packages from their'
                                      ' SRPMs for repo %s using %s jobs') %
                                      (len(src_repo_files), self.SRC_REPOS[repo_name], self._jobs),
                               logger=LOG)
            makefile_path = sh.joinpths(self.deps_dir, "binary-%s.mk" % repo_name)
            marks_dir = sh.joinpths(self.deps_dir, "marks-binary")
            if not sh.isdir(marks_dir):
                sh.mkdirslist(marks_dir, tracewriter=self.tracewriter)
            rpmbuild_flags = "--rebuild"
            if self.opts.get("usr_only", False):
                rpmbuild_flags += " --define 'usr_only 1'"
            params = {
                "SRC_REPO_DIR": src_repo_dir,
                "RPMBUILD_FLAGS": rpmbuild_flags,
                "LOGS_DIR": self.log_dir,
                'RPMTOP_DIR': self.rpmbuild_dir,
            }
            (_fn, content) = utils.load_template(sh.joinpths("packaging", "makefiles"), "binary.mk")
            sh.write_file(makefile_path, utils.expand_template(content, params),
                          tracewriter=self.tracewriter)
            with sh.remove_before_after(self.rpmbuild_dir):
                self._create_rpmbuild_subdirs()
                self._execute_make(makefile_path, marks_dir)
                repo_dir = sh.joinpths(self.anvil_repo_dir, repo_name)
                for d in sh.listdir(self.rpmbuild_dir, dirs_only=True):
                    self._move_rpm_files(sh.joinpths(d, "RPMS"), repo_dir)
                self._move_rpm_files(sh.joinpths(self.rpmbuild_dir, "RPMS"), repo_dir)
            self._create_repo(repo_name)

    def _execute_make(self, filename, marks_dir):
        cmdline = ["make", "-f", filename, "-j", str(self._jobs)]
        out_filename = sh.joinpths(self.log_dir, "%s.log" % sh.basename(filename))
        sh.execute_save_output(cmdline, cwd=marks_dir, out_filename=out_filename)

    def _move_srpms(self, repo_name, rpmbuild_dir=None):
        if rpmbuild_dir is None:
            rpmbuild_dir = self.rpmbuild_dir
        src_repo_name = self.SRC_REPOS[repo_name]
        src_repo_dir = sh.joinpths(self.anvil_repo_dir, src_repo_name)
        self._move_rpm_files(sh.joinpths(rpmbuild_dir, "SRPMS"), src_repo_dir)

    def _create_repo(self, repo_name):
        repo_dir = sh.joinpths(self.anvil_repo_dir, repo_name)
        src_repo_dir = sh.joinpths(self.anvil_repo_dir, self.SRC_REPOS[repo_name])
        for a_dir in (repo_dir, src_repo_dir):
            if not sh.isdir(a_dir):
                sh.mkdirslist(a_dir, tracewriter=self.tracewriter)
            cmdline = ["createrepo", a_dir]
            LOG.info("Creating repo at %s", a_dir)
            sh.execute(cmdline)
        repo_filename = sh.joinpths(self.anvil_repo_dir, "%s.repo" % repo_name)
        LOG.info("Writing %s", repo_filename)
        (_fn, content) = utils.load_template("packaging", "common.repo")
        params = {
            "repo_name": repo_name,
            "baseurl_bin": "file://%s" % repo_dir,
            "baseurl_src": "file://%s" % src_repo_dir,
        }
        sh.write_file(repo_filename, utils.expand_template(content, params),
                      tracewriter=self.tracewriter)
        # NOTE(harlowja): Install *.repo file so that anvil deps will be available
        # when building openstack core project packages.
        system_repo_filename = sh.joinpths(self.YUM_REPO_DIR, "%s.repo" % repo_name)
        sh.copy(repo_filename, system_repo_filename, tracewriter=self.tracewriter)
        LOG.info("Copied to %s", system_repo_filename)

    def _get_known_yum_packages(self):
        yum_map = collections.defaultdict(list)
        pkgs = []
        pkgs.extend(self.helper.list_available())
        pkgs.extend(self.helper.list_installed())
        for pkg in pkgs:
            for provides in pkg['provides']:
                yum_map[provides[0]].append((pkg['version'], pkg['repo']))
        # Note(harlowja): this is done to remove the default lists
        # that each entry would previously provide, converting the defaultdict
        # into a normal dict.
        return dict(yum_map)

    @staticmethod
    def _find_yum_match(yum_map, req, rpm_name):
        yum_versions = yum_map.get(rpm_name, [])
        for (version, repo) in yum_versions:
            if version in req:
                return (version, repo)
        return (None, None)

    def _filter_download_requires(self):
        yum_map = self._get_known_yum_packages()
        pip_origins = {}
        for line in self.pips_to_install:
            req = pip_helper.extract_requirement(line)
            pip_origins[req.key] = line

        pips_to_download = []
        req_to_install = [pip_helper.extract_requirement(line)
                          for line in self.pips_to_install]
        requested_names = [req.key for req in req_to_install]
        rpm_to_install = self._convert_names_python2rpm(requested_names)

        satisfied_list = []
        for (req, rpm_name) in zip(req_to_install, rpm_to_install):
            (version, repo) = self._find_yum_match(yum_map, req, rpm_name)
            if not repo:
                # We need the source requirement incase its a url.
                pips_to_download.append(pip_origins[req.key])
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

    def _build_dependencies(self):
        (pips_downloaded, package_files) = self.download_dependencies()

        # Analyze what was downloaded and eject things that were downloaded
        # by pip as a dependency of a download but which we do not want to
        # build or can satisfy by other means
        no_pips = [pkg_resources.Requirement.parse(name).key
                   for name in self.python_names]
        yum_map = self._get_known_yum_packages()
        pips_keys = set([p.key for p in pips_downloaded])

        def _filter_package_files(package_files):
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
                             "but it is disallowed."), colorizer.quote(req))
                    continue
                if req.key in pips_keys:
                    filtered_files.append(filename)
                    continue
                # See if pip tried to download it but we already can satisfy
                # it via yum and avoid building it in the first place...
                (_version, repo) = self._find_yum_match(yum_map, req, rpm_name)
                if not repo:
                    filtered_files.append(filename)
                else:
                    LOG.info(("Dependency %s was downloaded additionally "
                             "but it can be satisfied by %s from repository "
                             "%s instead."), colorizer.quote(req),
                             colorizer.quote(rpm_name),
                             colorizer.quote(repo))
            return filtered_files

        LOG.info("Filtering %s downloaded files.", len(package_files))
        filtered_package_files = _filter_package_files(package_files)
        if not filtered_package_files:
            LOG.info("No SRPM package dependencies to build.")
            return
        for filename in package_files:
            if filename not in filtered_package_files:
                sh.unlink(filename)
        package_files = sorted(filtered_package_files)

        # Now build them into SRPM rpm files.
        (_fn, content) = utils.load_template(sh.joinpths("packaging", "makefiles"), "source.mk")
        scripts_dir = sh.abspth(sh.joinpths(settings.TEMPLATE_DIR, "packaging", "scripts"))
        py2rpm_options = self._py2rpm_start_cmdline()[1:] + [
            "--scripts-dir", scripts_dir,
            "--source-only",
            "--rpm-base", self.rpmbuild_dir,
        ]
        params = {
            "DOWNLOADS_DIR": self.download_dir,
            "LOGS_DIR": self.log_dir,
            "PY2RPM": self.py2rpm_executable,
            "PY2RPM_FLAGS": " ".join(py2rpm_options),
        }
        marks_dir = sh.joinpths(self.deps_dir, "marks-deps")
        if not sh.isdir(marks_dir):
            sh.mkdirslist(marks_dir, tracewriter=self.tracewriter)
        makefile_path = sh.joinpths(self.deps_dir, "deps.mk")
        sh.write_file(makefile_path, utils.expand_template(content, params),
                      tracewriter=self.tracewriter)
        utils.log_iterable(package_files,
                           header="Building %s SRPM packages using %s jobs" % (len(package_files), self._jobs),
                           logger=LOG)
        self._execute_make(makefile_path, marks_dir)

    def _write_spec_file(self, instance, rpm_name, template_name, params):
        requires_what = params.get('requires')
        if not requires_what:
            requires_what = []
        requires_python = []
        try:
            requires_python.extend(instance.egg_info['dependencies'])
        except AttributeError:
            pass
        if requires_python:
            requires_what.extend(self._convert_names_python2rpm(requires_python, False))
        params['requires'] = requires_what
        params["epoch"] = self.OPENSTACK_EPOCH
        content = utils.load_template(self.SPEC_TEMPLATE_DIR, template_name)[1]
        spec_filename = sh.joinpths(self.rpmbuild_dir, "SPECS", "%s.spec" % rpm_name)
        sh.write_file(spec_filename, utils.expand_template(content, params),
                      tracewriter=self.tracewriter)
        return spec_filename

    def _copy_startup_scripts(self, instance, spec_filename):
        common_init_content = utils.load_template("packaging",
                                                  "common.init")[1]
        cmd = [self.specprint_executable]
        cmd.extend(['-f', spec_filename])
        daemon_args = instance.get_option('daemon_args', default_value={})
        spec_details = json.loads(sh.execute(cmd)[0])
        for src in spec_details.get('sources', []):
            script = sh.basename(src)
            if not (script.endswith(".init")):
                continue
            target_filename = sh.joinpths(self.rpm_sources_dir, script)
            if sh.isfile(target_filename):
                continue
            bin_name = utils.strip_prefix_suffix(script, "openstack-", ".init")
            params = {
                "bin": bin_name,
                "package": bin_name.split("-", 1)[0],
                "daemon_args": daemon_args.get(bin_name, ''),
            }
            sh.write_file(target_filename,
                          utils.expand_template(common_init_content, params))

    def _copy_sources(self, instance):
        other_sources_dir = sh.joinpths(settings.TEMPLATE_DIR,
                                        "packaging", "sources", instance.name)
        if sh.isdir(other_sources_dir):
            for filename in sh.listdir(other_sources_dir, files_only=True):
                sh.copy(filename, self.rpm_sources_dir)

    def _copy_patches(self, patches):
        for filename in patches:
            sh.copy(filename, self.rpm_sources_dir)

    def _build_from_spec(self, instance, spec_filename, patches=None):
        pkg_dir = instance.get_option('app_dir')
        if sh.isfile(sh.joinpths(pkg_dir, "setup.py")):
            self._write_python_tarball(instance, pkg_dir, ENSURE_NOT_MISSING)
        else:
            self._write_git_tarball(instance, pkg_dir, spec_filename)
        self._copy_sources(instance)
        if patches:
            self._copy_patches(patches)
        self._copy_startup_scripts(instance, spec_filename)
        cmdline = [
            self.rpmbuild_executable,
            "-bs",
            "--define", "_topdir %s" % self.rpmbuild_dir,
            spec_filename,
        ]
        out_filename = sh.joinpths(self.log_dir, "rpmbuild-%s.log" % instance.name)
        sh.execute_save_output(cmdline, out_filename=out_filename)

    def _write_git_tarball(self, instance, pkg_dir, spec_filename):
        cmdline = [
            "rpm",
            "-q",
            "--specfile", spec_filename,
            "--qf", "%{NAME}-%{VERSION}\n"
        ]
        tar_base = sh.execute(cmdline, cwd=pkg_dir)[0].splitlines()[0].strip()

        # NOTE(harlowja): git 1.7.1 from RHEL doesn't understand --format=tar.gz
        output_filename = sh.joinpths(self.rpm_sources_dir, "%s.tar" % tar_base)
        cmdline = [
            "git",
            "archive",
            "--format=tar",
            "--prefix=%s/" % tar_base,
            "--output=%s" % output_filename,
            "HEAD",
        ]
        out_filename = sh.joinpths(self.log_dir, "git-tar-%s.log" % instance.name)
        sh.execute_save_output(cmdline, cwd=pkg_dir, out_filename=out_filename)
        sh.gzip(output_filename)
        sh.unlink(output_filename)

    def _write_python_tarball(self, instance, pkg_dir, ensure_exists=None):

        def prefix_exists(text, in_what):
            for t in in_what:
                if t.startswith(text):
                    return True
            return False

        pkg_name = instance.egg_info['name']
        version = instance.egg_info['version']
        base_name = "%s-%s" % (pkg_name, version)
        cmdline = [
            sys.executable,
            "setup.py",
            "sdist",
            "--formats=tar",
            "--dist-dir", self.rpm_sources_dir,
        ]
        out_filename = sh.joinpths(self.log_dir, "sdist-%s.log" % (instance.name))
        sh.execute_save_output(cmdline, cwd=pkg_dir, out_filename=out_filename)
        archive_name = sh.joinpths(self.rpm_sources_dir, "%s.tar" % (base_name))
        if ensure_exists:
            with contextlib.closing(tarfile.open(archive_name, 'r')) as tfh:
                tar_entries = [t.path for t in tfh.getmembers()]
            missing_paths = {}
            for path in ensure_exists:
                tar_path = sh.joinpths(base_name, path)
                source_path = sh.joinpths(pkg_dir, path)
                if not prefix_exists(tar_path, tar_entries) and sh.exists(source_path):
                    missing_paths[tar_path] = source_path
            if missing_paths:
                utils.log_iterable(sorted(missing_paths.keys()),
                                   logger=LOG,
                                   header='%s paths were not archived and will now be' % (len(missing_paths)))
                with contextlib.closing(tarfile.open(archive_name, 'a')) as tfh:
                    for (tar_path, source_path) in missing_paths.items():
                        tfh.add(source_path, tar_path)
        sh.gzip(archive_name)
        sh.unlink(archive_name)

    @staticmethod
    def _is_client(instance_name, egg_name):
        for i in [instance_name, egg_name]:
            if i and i.endswith("client"):
                return True
        return False

    def _get_template_and_rpm_name(self, instance):
        rpm_name = None
        template_name = None
        try:
            egg_name = instance.egg_info['name']
            if self._is_client(instance.name, egg_name):
                rpm_name = egg_name
                template_name = "python-commonclient.spec"
            elif instance.name in self.SERVER_NAMES:
                rpm_name = "openstack-%s" % (egg_name)
            else:
                rpm_name = self.TRANSLATION_NAMES.get(instance.name)
        except AttributeError:
            rpm_name = instance.name
            template_name = "%s.spec" % rpm_name
        return (rpm_name, template_name)

    def _build_from_app_dir(self, instance, params):
        app_dir = instance.get_option('app_dir')
        cmdline = self._py2rpm_start_cmdline()
        cmdline.extend(["--source-only"])
        if 'release' in params:
            cmdline.extend(["--release", params["release"]])
        cmdline.extend(["--", app_dir])
        out_filename = sh.joinpths(self.log_dir, "py2rpm-build-%s.log" % (instance.name))
        sh.execute_save_output(cmdline, cwd=app_dir, out_filename=out_filename)

    def _build_openstack_package(self, instance):
        params = self._package_parameters(instance)
        patches = instance.list_patches("package")
        params['patches'] = [sh.basename(fn) for fn in patches]
        (rpm_name, template_name) = self._get_template_and_rpm_name(instance)
        try:
            egg_name = instance.egg_info['name']
            params["version"] = instance.egg_info["version"]
            if self._is_client(instance.name, egg_name):
                client_name = utils.strip_prefix_suffix(egg_name, "python-", "client")
                if not client_name:
                    msg = "Bad client package name %s" % (egg_name)
                    raise excp.PackageException(msg)
                params["clientname"] = client_name
                params["apiname"] = self.API_NAMES.get(client_name,
                                                       client_name.title())
        except AttributeError:
            spec_filename = None
            if template_name:
                spec_filename = sh.joinpths(settings.TEMPLATE_DIR,
                                            self.SPEC_TEMPLATE_DIR,
                                            template_name)
            if not spec_filename or not sh.isfile(spec_filename):
                rpm_name = None
        if rpm_name:
            if not template_name:
                template_name = "%s.spec" % rpm_name
            spec_filename = self._write_spec_file(instance, rpm_name,
                                                  template_name, params)
            self._build_from_spec(instance, spec_filename, patches)
        else:
            self._build_from_app_dir(instance, params)

    def _convert_names_python2rpm(self, python_names, only_name=True):
        if not python_names:
            return []
        cmdline = self._py2rpm_start_cmdline() + ["--convert"] + python_names
        rpm_names = []
        for line in sh.execute(cmdline)[0].splitlines():
            # format is "Requires: rpm-name <=> X"
            if not line.startswith("Requires:"):
                continue
            line = line[len("Requires:"):].strip()
            if only_name:
                positions = [line.find(">"), line.find("<"), line.find("=")]
                positions = sorted([p for p in positions if p != -1])
                if positions:
                    line = line[0:positions[0]].strip()
            if line and line not in rpm_names:
                rpm_names.append(line)
        return rpm_names

    def _desired_rpms_from_deps(self):
        # This file should have all the requirements (including test ones)
        # that we need to install (and which should have been built as rpms
        # in the previous build stages).
        gathered_requires = sh.load_file(self.gathered_requires_filename).splitlines()
        gathered_requires = [line.strip() for line in gathered_requires if line.strip()]
        req_names = []
        reqs = []
        for line in gathered_requires:
            req = pip_helper.extract_requirement(line)
            if req.key in req_names:
                continue
            req_names.append(req.key)
            reqs.append(req)
        rpm_names = self._convert_names_python2rpm(req_names)
        return zip(rpm_names, reqs)

    def _desired_rpms_from_instances(self):
        result = []
        need_names = []
        for inst in self.instances:
            if sh.isdir(inst.get_option("app_dir")):
                req = None
                rpm_name = None
                try:
                    (rpm_name, _tpl) = self._get_template_and_rpm_name(inst)
                    req = str(inst.egg_info['req'])
                    if rpm_name is not None:
                        result.append((rpm_name, req))
                    else:
                        need_names.append(req)
                except AttributeError:
                    pass
            for rpm_name in inst.package_names():
                result.append((rpm_name, None))
        if need_names:
            needed_rpm_names = self._convert_names_python2rpm(need_names)
            result.extend(zip(needed_rpm_names, need_names))
        result.extend((rpm_name, None) for rpm_name in self.requirements["requires"])
        return result

    def _get_rpm_names(self, from_deps=True, from_instances=True):
        # Ensure we select the right versions that is required and not a
        # version that doesn't match the requirements.
        desired_rpms = []
        if from_deps:
            desired_rpms.extend(self._desired_rpms_from_deps())
        if from_instances:
            desired_rpms.extend(self._desired_rpms_from_instances())

        def format_name(rpm_name, py_req):
            full_name = str(rpm_name).strip()
            if py_req is not None:
                full_name += ",%s" % (py_req)
            return full_name

        desired_rpms_formatted = sorted(format_name(rpm_name, py_req)
                                        for rpm_name, py_req in desired_rpms)
        desired_rpm_names = set(rpm_name for rpm_name, _py_req in desired_rpms)

        cmd = [self.yumfind_executable, '-j']
        for p in desired_rpms_formatted:
            cmd.extend(['-p', p])
        header = "Validating %s required packages are still available" % (len(desired_rpms))
        utils.log_iterable(desired_rpms_formatted, header=header, logger=LOG)

        rpms_located = []
        rpm_names_located = set()
        for matched in sh.execute(cmd)[0].splitlines():
            matched = matched.strip()
            if matched:
                pkg = json.loads(matched)
                if isinstance(pkg, dict):
                    rpm_names_located.add(pkg['req_name'])
                    rpms_located.append(pkg)

        rpm_names_missing = desired_rpm_names - rpm_names_located
        if rpm_names_missing:
            # Include the python version required information (if applicable)
            missing_formatted = []
            for n in sorted(rpm_names_missing):
                source_found = False
                for (n2, py_req) in desired_rpms:
                    if n2 == n:
                        missing_formatted.append(format_name(n2, py_req))
                        source_found = True
                        break
                if not source_found:
                    missing_formatted.append(format_name(n, None))
            msg = "Could not find available rpm packages: %s"
            msg = msg % (", ".join(missing_formatted))
            raise excp.DependencyException(msg)

        LOG.info("All %s required packages are still available!", len(desired_rpms))
        desired_rpms = []
        for pkg in rpms_located:
            LOG.debug("Found %s", pkg)
            desired_rpms.append("%s,%s" % (pkg['name'], pkg['version']))
        return list(sorted(desired_rpms))

    def install(self, general):
        super(YumDependencyHandler, self).install(general)
        self.helper.clean()

        install_all_deps = general.get_bool_option('install-all-deps', True)
        install_pkgs = self._get_rpm_names(from_deps=install_all_deps,
                                           from_instances=True)

        # Erase conflicting packages
        remove_pkgs = [pkg_name
                       for pkg_name in self.requirements["conflicts"]
                       if self.helper.is_installed(pkg_name)]
        self.helper.transaction(install_pkgs=install_pkgs,
                                remove_pkgs=remove_pkgs,
                                tracewriter=self.tracewriter)

    def install_all_deps(self):
        super(YumDependencyHandler, self).install_all_deps()
        self.helper.clean()
        install_pkgs = self._get_rpm_names(from_deps=True, from_instances=False)
        self.helper.transaction(install_pkgs=install_pkgs,
                                tracewriter=self.tracewriter)

    def uninstall(self):
        super(YumDependencyHandler, self).uninstall()
        if self.tracereader.exists():
            remove_pkgs = self.tracereader.packages_installed()
            self.helper.transaction(remove_pkgs=remove_pkgs)
