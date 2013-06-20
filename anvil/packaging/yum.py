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

from anvil import colorizer
from anvil import env
from anvil import exceptions as excp
from anvil import log as logging
from anvil.packaging import base
from anvil.packaging.helpers import pip_helper
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
    TRANSLATION_NAMES = {
        'horizon': "python-django-horizon",
    }
    REPO_FN = "anvil.repo"
    YUM_REPO_DIR = "/etc/yum.repos.d/"
    BANNED_PACKAGES = [
        'distribute',
        'setuptools',
    ]
    py2rpm_executable = sh.which("py2rpm", ["tools/"])
    rpmbuild_executable = sh.which("rpmbuild")

    def __init__(self, distro, root_dir, instances):
        super(YumDependencyHandler, self).__init__(distro, root_dir, instances)
        self.rpmbuild_dir = sh.joinpths(self.deps_dir, "rpmbuild")
        self.deps_repo_dir = sh.joinpths(self.deps_dir, "openstack-deps")
        self.deps_src_repo_dir = sh.joinpths(self.deps_dir, "openstack-deps-sources")
        self.anvil_repo_filename = sh.joinpths(self.deps_dir, self.REPO_FN)
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
        return params

    def package_instance(self, instance):
        with sh.remove_before_after(self.rpmbuild_dir):
            for dirname in (sh.joinpths(self.rpmbuild_dir, "SPECS"),
                            sh.joinpths(self.rpmbuild_dir, "SOURCES")):
                sh.mkdirslist(dirname, tracewriter=self.tracewriter)
            if instance.name in ["general"]:
                self._build_dependencies()
                self._move_rpms("anvil-deps")
                self._create_repo("anvil-deps")
            else:
                # Meta packages don't get built.
                app_dir = instance.get_option("app_dir")
                if sh.isdir(app_dir):
                    self._build_openstack_package(instance)
                    self._move_rpms("anvil")

    def package_finish(self):
        self._create_repo("anvil")

    def _move_rpms(self, repo_name):
        repo_dir = sh.joinpths(self.anvil_repo_dir, repo_name)
        src_repo_dir = "%s-sources" % repo_dir
        for dirname in (repo_dir, src_repo_dir):
            sh.mkdirslist(dirname, tracewriter=self.tracewriter)
        for (src_dir, tgt_dir) in ([sh.joinpths(self.rpmbuild_dir, "RPMS"), repo_dir],
                                   [sh.joinpths(self.rpmbuild_dir, "SRPMS"), src_repo_dir]):
            rpms = []
            for filename in sh.listdir(src_dir, recursive=True, files_only=True):
                sh.move(filename, tgt_dir, force=True)
                rpms.append(sh.basename(filename))
            if rpms:
                utils.log_iterable(rpms,
                                   header="Moved %s rpms to %s" % (len(rpms),
                                                                   tgt_dir),
                                   logger=LOG)

    def _create_repo(self, repo_name):
        repo_dir = sh.joinpths(self.anvil_repo_dir, repo_name)
        src_repo_dir = "%s-sources" % repo_dir
        for a_dir in (repo_dir, src_repo_dir):
            cmdline = ["createrepo", a_dir]
            LOG.info("Creating repo at %s", a_dir)
            sh.execute(cmdline)
        repo_filename = sh.joinpths(self.anvil_repo_dir, "%s.repo" % repo_name)
        LOG.info("Writing %s", repo_filename)
        (_fn, content) = utils.load_template("packaging", "common.repo")
        params = {
            "repo_name": repo_name,
            "baseurl_bin": "file://%s" % repo_dir,
            "baseurl_src": "file://%s" % src_repo_dir
        }
        sh.write_file(repo_filename,
                      utils.expand_template(content, params),
                      tracewriter=self.tracewriter)

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
        package_files = filter_package_files(package_files)
        if not package_files:
            LOG.info("No RPM packages of OpenStack dependencies to build")
            return
        package_base_names = [sh.basename(f) for f in package_files]
        utils.log_iterable(sorted(package_base_names), logger=LOG,
                           header=("Building %s dependency RPM"
                                   " packages") % (len(package_files)))
        scripts_dir = sh.abspth(sh.joinpths(settings.TEMPLATE_DIR,
                                            "packaging", "scripts"))
        with utils.progress_bar(name='Building',
                                max_am=len(package_files)) as p_bar:
            for (i, filename) in enumerate(sorted(package_files)):
                cmdline = self.py2rpm_start_cmdline()
                cmdline.extend(["--scripts-dir", scripts_dir])
                cmdline.extend(["--", filename])
                build_filename = "py2rpm-%s.out" % sh.basename(filename)
                out_filename = sh.joinpths(self.log_dir, build_filename)
                sh.execute_save_output(cmdline, out_filename=out_filename,
                                       quiet=True)
                p_bar.update(i + 1)

    def _write_spec_file(self, instance, rpm_name, template_name, params):
        app_dir = instance.get_option('app_dir')
        requires_what = []
        try:
            requires_what.extend(instance.egg_info['dependencies'])
        except AttributeError:
            pass
        # Ensure we include any extra pips that are desired.
        extra_pips = instance.get_option('pips') or []
        for i_pip in extra_pips:
            extra_req = pip_helper.create_requirement(i_pip['name'],
                                                      i_pip.get('version'))
            extra_req = str(extra_req)
            if extra_req not in requires_what:
                requires_what.append(extra_req)
        params['requires'] = self._convert_names_python2rpm(requires_what)
        params["epoch"] = self.OPENSTACK_EPOCH
        content = utils.load_template(self.SPEC_TEMPLATE_DIR, template_name)[1]
        spec_filename = sh.joinpths(self.rpmbuild_dir, "SPECS",
                                    "%s.spec" % rpm_name)
        sh.write_file(spec_filename,
                      utils.expand_template(content, params),
                      tracewriter=self.tracewriter)
        return spec_filename

    def _copy_startup_scripts(self, spec_filename):
        common_init_content = utils.load_template("packaging",
                                                  "common.init")[1]
        for src in rpm.spec(spec_filename).sources:
            script = sh.basename(src[0])
            if not (script.endswith(".init")):
                continue
            target_filename = sh.joinpths(self.rpm_sources_dir, script)
            if sh.isfile(target_filename):
                continue
            bin_name = utils.strip_prefix_suffix(script, "openstack-", ".init")
            params = {
                "bin": bin_name,
                "package": bin_name.split("-", 1)[0],
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
            "-ba",
            "--define", "_topdir %s" % self.rpmbuild_dir,
            spec_filename,
        ]
        sh.execute_save_output(cmdline,
                               sh.joinpths(self.log_dir,
                                           sh.basename(spec_filename)),
                               quiet=True)

    def _write_git_tarball(self, pkg_dir, spec_filename):
        cmdline = [
            "rpm",
            "-q",
            "--specfile", spec_filename,
            "--qf", "%{NAME}-%{VERSION}\n"
        ]
        tar_base = sh.execute(cmdline, cwd=pkg_dir)[0].splitlines()[0].strip()
        # git 1.7.1 from RHEL doesn't understand --format=tar.gz
        output_filename = sh.joinpths(self.rpm_sources_dir,
                                      "%s.tar" % tar_base)
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

    def _build_openstack_package(self, instance):
        params = self._package_parameters(instance)
        patches = instance.list_patches("package")
        params['patches'] = [sh.basename(fn) for fn in patches]
        (rpm_name, template_name) = self._get_template_and_rpm_name(instance)
        try:
            egg_name = instance.egg_info['name']
            params["version"] = instance.egg_info["version"]
            if self._is_client(instance.name, egg_name):
                client_name = utils.strip_prefix_suffix(egg_name,
                                                        "python-", "client")
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
            app_dir = instance.get_option('app_dir')
            cmdline = self.py2rpm_start_cmdline() + ["--", app_dir]
            sh.execute_save_output(cmdline,
                                   cwd=app_dir,
                                   out_filename=sh.joinpths(self.log_dir,
                                                            instance.name),
                                   quiet=True)

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
        # This file should have all the requirements (including test ones)
        # that we need to install (and which should have been built as rpms
        # in the previous build stages).
        gathered_requires = sh.load_file(self.gathered_requires_filename).splitlines()
        gathered_requires = [line.strip() for line in gathered_requires if line.strip()]
        req_names = []
        for line in gathered_requires:
            req = pip_helper.extract_requirement(line)
            req_names.append(req.key)
        rpm_names = set(self._convert_names_python2rpm(req_names))
        for inst in self.instances:
            rpm_names |= inst.package_names()
        return list(rpm_names)

    def install(self):
        super(YumDependencyHandler, self).install()

        # Ensure we copy the local repo file name to the main repo so that
        # yum will find it when installing packages.
        for repo_name in "anvil", "anvil-deps":
            repo_filename = sh.joinpths(
                self.anvil_repo_dir, "%s.repo" % repo_name)
            if sh.isfile(repo_filename):
                sh.write_file(
                    "%s/%s.repo" % (self.YUM_REPO_DIR, repo_name),
                    sh.load_file(repo_filename),
                    tracewriter=self.tracewriter)

        # Erase it if its been previously installed.
        cmdline = []
        for p in self.nopackages:
            if self.helper.is_installed(p):
                cmdline.append(p)

        if cmdline:
            cmdline = ["yum", "erase", "-y"] + cmdline
            sh.execute(cmdline, stdout_fh=sys.stdout, stderr_fh=sys.stderr)

        cmdline = ["yum", "clean", "all"]
        sh.execute(cmdline)

        rpm_names = self._all_rpm_names()
        if rpm_names:
            cmdline = ["yum", "install", "-y"] + rpm_names
            sh.execute(cmdline, stdout_fh=sys.stdout, stderr_fh=sys.stderr)

    def uninstall(self):
        super(YumDependencyHandler, self).uninstall()

        # Don't take out packages that anvil requires to run...
        no_remove = env.get_key('REQUIRED_PACKAGES', '').split()
        no_remove = sorted(set(no_remove))

        scan_packages = self._all_rpm_names()
        rpm_names = []
        for p in scan_packages:
            if p in no_remove:
                continue
            if self.helper.is_installed(p):
                rpm_names.append(p)

        if rpm_names:
            cmdline = ["yum", "remove", "--remove-leaves", "-y"]
            for p in no_remove:
                cmdline.append("--exclude=%s" % (p))
            cmdline.extend(sorted(set(rpm_names)))
            sh.execute(cmdline, stdout_fh=sys.stdout, stderr_fh=sys.stderr)
