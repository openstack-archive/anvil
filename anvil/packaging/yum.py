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
import errno
import json
import pkg_resources
import sys
import tarfile

import six

from anvil import colorizer
from anvil import exceptions as excp
from anvil import log as logging
from anvil.packaging import base
from anvil.packaging.helpers import envra_helper
from anvil.packaging.helpers import pip_helper
from anvil.packaging.helpers import py2rpm_helper
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
_DEFAULT_SKIP_EPOCHS = ['0']


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
    YUM_REPO_DIR = "/etc/yum.repos.d/"
    SRC_REPOS = {
        'anvil': 'anvil-source',
        "anvil-deps": "anvil-deps-source",
    }
    REPOS = ["anvil-deps", "anvil"]
    JOBS = 2

    def __init__(self, distro, root_dir, instances, opts):
        super(YumDependencyHandler, self).__init__(distro, root_dir, instances, opts)
        # Various paths we will use while operating
        self.rpmbuild_dir = sh.joinpths(self.deps_dir, "rpmbuild")
        self.prebuild_dir = sh.joinpths(self.deps_dir, "prebuild")
        self.deps_repo_dir = sh.joinpths(self.deps_dir, "openstack-deps")
        self.deps_src_repo_dir = sh.joinpths(self.deps_dir, "openstack-deps-sources")
        self.rpm_sources_dir = sh.joinpths(self.rpmbuild_dir, "SOURCES")
        self.anvil_repo_dir = sh.joinpths(self.root_dir, "repo")
        self.build_requires_filename = sh.joinpths(self.deps_dir, "build-requires")
        self.yum_satisfies_filename = sh.joinpths(self.deps_dir, "yum-satisfiable")
        self.rpm_build_requires_filename = sh.joinpths(self.deps_dir, "rpm-build-requires")
        # Executables we require to operate
        self.rpmbuild_executable = sh.which("rpmbuild")
        self.specprint_executable = sh.which('specprint', ["tools/"])
        # We inspect yum for packages, this helper allows us to do this.
        self.helper = yum_helper.Helper(self.log_dir, self.REPOS)
        self.envra_helper = envra_helper.Helper()
        # See if we are requested to run at a higher make parallelism level
        try:
            self.jobs = max(self.JOBS, int(self.opts.get('jobs')))
        except (TypeError, ValueError):
            self.jobs = self.JOBS

    def _fetch_epoch_mapping(self):
        epoch_map = self.distro.get_dependency_config("epoch_map", quiet=True)
        if not epoch_map:
            epoch_map = {}
        epoch_skips = self.distro.get_dependency_config("epoch_skips",
                                                        quiet=True)
        if not epoch_skips:
            epoch_skips = _DEFAULT_SKIP_EPOCHS
        if not isinstance(epoch_skips, (list, tuple)):
            epoch_skips = [i.strip() for i in epoch_skips.split(",")]
        built_epochs = {}
        for name in self.python_names:
            if name in epoch_map:
                built_epochs[name] = str(epoch_map.pop(name))
            else:
                built_epochs[name] = str(self.OPENSTACK_EPOCH)
        # Ensure epochs set by a yum searching (that are not in the list of
        # epochs to provide) are correctly set when building dependent
        # packages...
        keep_names = set()
        try:
            yum_satisfies = sh.load_file(self.yum_satisfies_filename)
        except IOError as e:
            if e.errno != errno.ENOENT:
                raise
        else:
            for line in yum_satisfies.splitlines():
                raw_req_rpm = utils.parse_json(line)
                req = pip_helper.extract_requirement(raw_req_rpm['requirement'])
                if req.key in epoch_map:
                    LOG.debug("Ensuring manually set epoch is retained for"
                              " requirement '%s' with epoch %s", req,
                              epoch_map[req.key])
                    keep_names.add(req.key)
                else:
                    rpm_info = raw_req_rpm['rpm']
                    rpm_epoch = rpm_info.get('epoch')
                    if rpm_epoch and str(rpm_epoch) not in epoch_skips:
                        LOG.debug("Adding in yum satisfiable package %s for"
                                  " requirement '%s' with epoch %s from repo %s",
                                  rpm_info['name'], req, rpm_epoch, rpm_info['repo'])
                        keep_names.add(req.key)
                        epoch_map[req.key] = str(rpm_epoch)
        # Exclude names from the epoch map that we never downloaded in the
        # first place or that we did not just set automatically (since these
        # are not useful and should not be set in the first place).
        try:
            raw_downloaded = sh.load_file(self.build_requires_filename)
            downloaded_reqs = pip_helper.parse_requirements(raw_downloaded)
        except IOError as e:
            if e.errno != errno.ENOENT:
                raise
        else:
            downloaded_names = set([req.key for req in downloaded_reqs])
            tmp_epoch_map = {}
            for (name, epoch) in six.iteritems(epoch_map):
                name = name.lower()
                if name in downloaded_names or name in keep_names:
                    tmp_epoch_map[name] = str(epoch)
                else:
                    LOG.debug("Discarding %s:%s from the epoch mapping since"
                              " it was not part of the downloaded (or automatically"
                              " included) build requirements", name, epoch)
            epoch_map = tmp_epoch_map
        epoch_map.update(built_epochs)
        return epoch_map

    @property
    def py2rpm_helper(self):
        epoch_map = self._fetch_epoch_mapping()
        package_map = self.distro.get_dependency_config("package_map")
        arch_dependent = self.distro.get_dependency_config("arch_dependent")
        build_options = self.distro.get_dependency_config("build_options")
        return py2rpm_helper.Helper(epoch_map=epoch_map,
                                    package_map=package_map,
                                    arch_dependent=arch_dependent,
                                    rpmbuild_dir=self.rpmbuild_dir,
                                    download_dir=self.download_dir,
                                    deps_dir=self.deps_dir,
                                    log_dir=self.log_dir,
                                    build_options=build_options)

    def _package_parameters(self, instance):
        params = {}
        params["release"] = str(instance.get_option("release", default_value=1))
        if '-' in params["release"]:
            # NOTE(imelnikov): "-" is prohibited in RPM releases
            raise ValueError("Malformed package release: %r" % params["release"])
        version_suffix = instance.get_option("version_suffix", default_value="")
        if version_suffix and not version_suffix.startswith('.'):
            version_suffix = '.' + version_suffix
        params['version_suffix'] = version_suffix
        tests_package = instance.get_option('tests_package', default_value={})

        params["no_tests"] = 0 if tests_package.get('enabled', True) else 1
        params["exclude_from_test_env"] = ['./bin', './build*']
        params["exclude_from_test_env"].extend(
            tests_package.get("exclude_from_env", ()))
        return params

    def _create_rpmbuild_subdirs(self):
        for dirname in (sh.joinpths(self.rpmbuild_dir, "SPECS"),
                        sh.joinpths(self.rpmbuild_dir, "SOURCES")):
            sh.mkdirslist(dirname, tracewriter=self.tracewriter)

    def package_instance(self, instance):
        with sh.remove_before(self.rpmbuild_dir):
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
            return 0
        moved = 0
        for filename in sh.listdir(source_dir, recursive=True, files_only=True):
            if not filename.lower().endswith(".rpm"):
                continue
            sh.move(filename, target_dir, force=True)
            moved += 1
        return moved

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

        def move_rpms(repo_name):
            repo_dir = sh.joinpths(self.anvil_repo_dir, repo_name)
            search_dirs = [
                sh.joinpths(self.rpmbuild_dir, "RPMS"),
            ]
            for sub_dir in sh.listdir(self.rpmbuild_dir, dirs_only=True):
                search_dirs.append(sh.joinpths(sub_dir, "RPMS"))
            moved = 0
            for source_dir in search_dirs:
                moved += self._move_rpm_files(source_dir, repo_dir)
            return moved

        def build(repo_dir, repo_name, header_tpl):
            repo_files = list_src_rpms(repo_dir)
            if not repo_files:
                return
            utils.log_iterable(repo_files,
                               header=header_tpl % (len(repo_files),
                                                    self.SRC_REPOS[repo_name],
                                                    self.jobs),
                               logger=LOG)
            rpmbuild_flags = "--rebuild"
            if self.opts.get("usr_only", False):
                rpmbuild_flags += " --define 'usr_only 1'"
            with sh.remove_before(self.rpmbuild_dir):
                self._create_rpmbuild_subdirs()
                try:
                    self.py2rpm_helper.build_all_binaries(repo_name,
                                                          repo_dir,
                                                          rpmbuild_flags,
                                                          self.tracewriter,
                                                          self.jobs)
                finally:
                    # If we made any rpms (even if a failure happened, make
                    # sure that we move them to the right target repo).
                    if move_rpms(repo_name) > 0:
                        self._create_repo(repo_name)

        def pre_build():
            build_requirements = self.requirements.get("build-requires")
            if build_requirements:
                utils.log_iterable(build_requirements,
                                   header="Installing build requirements",
                                   logger=LOG)
                self.helper.transaction(install_pkgs=build_requirements,
                                        tracewriter=self.tracewriter)
            build_requirements = ''
            try:
                build_requirements = sh.load_file(self.rpm_build_requires_filename)
            except IOError as e:
                if e.errno != errno.ENOENT:
                    raise
            build_requirements = set(pkg_resources.yield_lines(build_requirements))
            for repo_name in self.REPOS:
                repo_dir = sh.joinpths(self.anvil_repo_dir, self.SRC_REPOS[repo_name])
                matched_paths = []
                paths = list_src_rpms(repo_dir)
                envra_details = self.envra_helper.explode(*paths)
                for (path, envra_detail) in zip(paths, envra_details):
                    package_name = envra_detail.get('name')
                    if package_name in build_requirements:
                        matched_paths.append(path)
                        build_requirements.discard(package_name)
                if matched_paths:
                    with sh.remove_before(self.prebuild_dir) as prebuild_dir:
                        if not sh.isdir(prebuild_dir):
                            sh.mkdirslist(prebuild_dir, tracewriter=self.tracewriter)
                        for path in matched_paths:
                            sh.move(path, sh.joinpths(prebuild_dir, sh.basename(path)))
                        build(prebuild_dir, repo_name,
                              'Prebuilding %s RPM packages from their SRPMs'
                              ' for repo %s using %s jobs')
            return build_requirements

        unsatisfied_build_requirements = list(pre_build())
        if unsatisfied_build_requirements:
            utils.log_iterable(sorted(unsatisfied_build_requirements),
                               header="%s unsatisfied build requirements (these"
                                      " will need to be satisfied by existing"
                                      " repositories)" % len(unsatisfied_build_requirements),
                               logger=LOG)
        for repo_name in self.REPOS:
            repo_dir = sh.joinpths(self.anvil_repo_dir, self.SRC_REPOS[repo_name])
            build(repo_dir, repo_name,
                  'Building %s RPM packages from their SRPMs for repo %s'
                  ' using %s jobs')

    def _move_srpms(self, repo_name, rpmbuild_dir=None):
        if rpmbuild_dir is None:
            rpmbuild_dir = self.rpmbuild_dir
        src_repo_name = self.SRC_REPOS[repo_name]
        src_repo_dir = sh.joinpths(self.anvil_repo_dir, src_repo_name)
        return self._move_rpm_files(sh.joinpths(rpmbuild_dir, "SRPMS"),
                                    src_repo_dir)

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
        LOG.info("Determining which yum packages are available or installed...")
        yum_map = collections.defaultdict(list)
        pkgs = []
        pkgs.extend(self.helper.list_available())
        pkgs.extend(self.helper.list_installed())
        for pkg in pkgs:
            for provides in pkg.get('provides', []):
                yum_map[provides[0]].append(pkg)
        # Note(harlowja): this is done to remove the default lists
        # that each entry would previously provide, converting the defaultdict
        # into a normal dict.
        return dict(yum_map)

    @staticmethod
    def _find_yum_match(yum_map, req, rpm_name):
        yum_versions = yum_map.get(rpm_name, [])
        for pkg in yum_versions:
            version = pkg['version']
            if version in req:
                return pkg
        return None

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
        rpm_names = self.py2rpm_helper.names_to_rpm_names(requested_names)

        satisfied_list = []
        for req in req_to_install:
            rpm_name = rpm_names[req.key]
            rpm_info = self._find_yum_match(yum_map, req, rpm_name)
            if not rpm_info:
                # We need the source requirement in case it's a url.
                pips_to_download.append(pip_origins[req.key])
            else:
                satisfied_list.append((req, rpm_name, rpm_info))

        yum_buff = six.StringIO()
        if satisfied_list:
            # Organize by repo
            repos = collections.defaultdict(list)
            for (req, rpm_name, rpm_info) in satisfied_list:
                repo = rpm_info['repo']
                rpm_found = '%s-%s' % (rpm_name, rpm_info['version'])
                repos[repo].append("%s as %s" % (colorizer.quote(req),
                                                 colorizer.quote(rpm_found)))
                dep_info = {
                    'requirement': str(req),
                    'rpm': rpm_info,
                }
                yum_buff.write(json.dumps(dep_info))
                yum_buff.write("\n")
            for r in sorted(repos.keys()):
                header = ("%s Python packages are already available "
                          "as RPMs from repository %s")
                header = header % (len(repos[r]), colorizer.quote(r))
                utils.log_iterable(sorted(repos[r]), logger=LOG, header=header,
                                   color=None)
        sh.write_file(self.yum_satisfies_filename, yum_buff.getvalue())
        return pips_to_download

    def _build_dependencies(self):
        (pips_downloaded, package_files) = self.download_dependencies()

        # Analyze what was downloaded and eject things that were downloaded
        # by pip as a dependency of a download but which we do not want to
        # build or can satisfy by other means
        no_pips = [pkg_resources.Requirement.parse(name).key
                   for name in self.python_names]
        no_pips.extend(self.ignore_pips)
        yum_map = self._get_known_yum_packages()
        pips_keys = set([p.key for p in pips_downloaded])
        package_reqs = []
        for filename in package_files:
            package_details = pip_helper.get_archive_details(filename)
            package_reqs.append((filename, package_details['req']))

        def _filter_package_files():
            yum_provided = []
            req_names = [req.key for (filename, req) in package_reqs]
            package_rpm_names = self.py2rpm_helper.names_to_rpm_names(req_names)
            filtered_files = []
            for filename, req in package_reqs:
                rpm_name = package_rpm_names[req.key]
                if req.key in no_pips:
                    LOG.info(("Dependency %s was downloaded additionally "
                             "but it is disallowed."), colorizer.quote(req))
                    continue
                if req.key in pips_keys:
                    filtered_files.append(filename)
                    continue
                # See if pip tried to download it but we already can satisfy
                # it via yum and avoid building it in the first place...
                rpm_info = self._find_yum_match(yum_map, req, rpm_name)
                if not rpm_info:
                    filtered_files.append(filename)
                else:
                    yum_provided.append((req, rpm_info))
                    LOG.info(("Dependency %s was downloaded additionally "
                              "but it can be satisfied by %s from repository "
                              "%s instead."), colorizer.quote(req),
                             colorizer.quote(rpm_name),
                             colorizer.quote(rpm_info['repo']))
            return (filtered_files, yum_provided)

        LOG.info("Filtering %s downloaded files.", len(package_files))
        filtered_package_files, yum_provided = _filter_package_files()
        if yum_provided:
            yum_buff = six.StringIO()
            for (req, rpm_info) in yum_provided:
                dep_info = {
                    'requirement': str(req),
                    'rpm': rpm_info,
                }
                yum_buff.write(json.dumps(dep_info))
                yum_buff.write("\n")
            sh.append_file(self.yum_satisfies_filename, yum_buff.getvalue())
        if not filtered_package_files:
            LOG.info("No SRPM package dependencies to build.")
            return
        for filename in package_files:
            if filename not in filtered_package_files:
                sh.unlink(filename)

        ensure_prebuilt = self.distro.get_dependency_config("ensure_prebuilt",
                                                            quiet=True)
        if not ensure_prebuilt:
            ensure_prebuilt = {}
        build_requires = six.StringIO()
        rpm_build_requires = six.StringIO()
        for (filename, req) in package_reqs:
            if filename in filtered_package_files:
                build_requires.write("%s # %s\n" % (req, sh.basename(filename)))
                prebuilt_reqs = []
                for line in ensure_prebuilt.get(req.key, []):
                    prebuilt_reqs.append(pip_helper.extract_requirement(line))
                if prebuilt_reqs:
                    rpm_build_requires.write("# %s from %s\n" % (req, sh.basename(filename)))
                    rpm_names = self.py2rpm_helper.names_to_rpm_names(
                        [r.key for r in prebuilt_reqs])
                    for r in prebuilt_reqs:
                        rpm_name = rpm_names[r.key]
                        LOG.info("Adding %s (%s) as a pre-build time"
                                 " requirement of %s (%s)", r, rpm_name, req,
                                 sh.basename(filename))
                        rpm_build_requires.write("%s # %s\n" % (rpm_name, r))
                    rpm_build_requires.write("\n")

        sh.append_file(self.rpm_build_requires_filename, rpm_build_requires.getvalue())
        sh.write_file(self.build_requires_filename, build_requires.getvalue())

        # Now build them into SRPM rpm files.
        package_files = sorted(filtered_package_files)
        self.py2rpm_helper.build_all_srpms(package_files=package_files,
                                           tracewriter=self.tracewriter,
                                           jobs=self.jobs)

    def _make_spec_functors(self, downloaded_version):
        # TODO(harlowja): refactor to just use cmp()

        def newer_than(version):
            version = pkg_resources.parse_version(version)
            if downloaded_version > version:
                return True
            return False

        def newer_than_eq(version):
            version = pkg_resources.parse_version(version)
            if downloaded_version >= version:
                return True
            return False

        def older_than(version):
            version = pkg_resources.parse_version(version)
            if downloaded_version < version:
                return True
            return False

        def older_than_eq(version):
            version = pkg_resources.parse_version(version)
            if downloaded_version <= version:
                return True
            return False

        return {
            'older_than_eq': older_than_eq,
            'older_than': older_than,
            'newer_than_eq': newer_than_eq,
            'newer_than': newer_than,
        }

    def _write_spec_file(self, instance, rpm_name, template_name, params):
        requires_what = params.get('requires', [])
        test_requires_what = params.get('test_requires', [])
        egg_info = getattr(instance, 'egg_info', None)
        if egg_info:

            def ei_names(key):
                try:
                    requires_python = [str(req) for req in egg_info[key]]
                except KeyError:
                    return []
                else:
                    return self.py2rpm_helper.names_to_rpm_requires(requires_python)

            requires_what.extend(ei_names('dependencies'))
            test_requires_what.extend(ei_names('test_dependencies'))

        params["requires"] = requires_what
        params["test_requires"] = test_requires_what
        params["epoch"] = self.OPENSTACK_EPOCH
        params["part_fn"] = lambda filename: sh.joinpths(
            settings.TEMPLATE_DIR,
            self.SPEC_TEMPLATE_DIR,
            filename)
        parsed_version = pkg_resources.parse_version(params["version"])
        params.update(self._make_spec_functors(parsed_version))
        content = utils.load_template(self.SPEC_TEMPLATE_DIR, template_name)[1]
        spec_filename = sh.joinpths(self.rpmbuild_dir, "SPECS", "%s.spec" % rpm_name)
        sh.write_file(spec_filename, utils.expand_template(content, params),
                      tracewriter=self.tracewriter)
        return spec_filename

    def _copy_startup_scripts(self, instance, spec_details):
        common_init_content = utils.load_template("packaging",
                                                  "common.init")[1]
        daemon_args = instance.get_option('daemon_args', default_value={})
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

    def _copy_systemd_scripts(self, instance, spec_details):
        common_init_content = utils.load_template("packaging",
                                                  "common.service")[1]
        daemon_args = instance.get_option('daemon_args', default_value={})
        for src in spec_details.get('sources', []):
            script = sh.basename(src)
            if not (script.endswith(".service")):
                continue
            target_filename = sh.joinpths(self.rpm_sources_dir, script)
            if sh.isfile(target_filename):
                continue
            bin_name = utils.strip_prefix_suffix(script, "openstack-", ".service")
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
        cmdline = [self.specprint_executable]
        cmdline.extend(['-f', spec_filename])
        spec_details = json.loads(sh.execute(cmdline)[0])
        rpm_requires = []
        for k in ('requires', 'requirenevrs'):
            try:
                rpm_requires.extend(spec_details['headers'][k])
            except (KeyError, TypeError):
                pass
        if rpm_requires:
            buff = six.StringIO()
            buff.write("# %s\n" % instance.name)
            if rpm_requires:
                for req in rpm_requires:
                    buff.write("%s\n" % req)
                buff.write("\n")
            sh.append_file(self.rpm_build_requires_filename, buff.getvalue())
        self._copy_startup_scripts(instance, spec_details)
        self._copy_systemd_scripts(instance, spec_details)
        cmdline = [
            self.rpmbuild_executable,
            "-bs",
            "--define", "_topdir %s" % self.rpmbuild_dir,
            spec_filename,
        ]
        out_filename = sh.joinpths(self.log_dir, "rpmbuild-%s.log" % instance.name)
        sh.execute_save_output(cmdline, out_filename)

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
        sh.execute_save_output(cmdline, out_filename, cwd=pkg_dir)
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
        sh.execute_save_output(cmdline, out_filename, cwd=pkg_dir)
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

    def _find_template_and_rpm_name(self, instance, build_name):
        search_names = [(build_name, "%s.spec" % build_name)]

        try:
            egg_name = instance.egg_info['name']
        except AttributeError:
            pass
        else:
            if any(s.endswith("client")
                   for s in (instance.name, egg_name, build_name)):
                search_names.append([egg_name, "python-commonclient.spec"])
            search_names.extend([
                ("openstack-%s" % (egg_name), "openstack-%s.spec" % (egg_name)),
                (egg_name, "%s.spec" % (egg_name)),
            ])

        # Return the first that exists (if any from this list)
        for (rpm_name, template_name) in search_names:
            spec_filename = sh.joinpths(settings.TEMPLATE_DIR,
                                        self.SPEC_TEMPLATE_DIR, template_name)
            if sh.isfile(spec_filename):
                return (rpm_name, template_name)
        return (None, None)

    def _build_openstack_package(self, instance):
        params = self._package_parameters(instance)
        patches = instance.list_patches("package")
        params['patches'] = [sh.basename(fn) for fn in patches]

        build_name = instance.get_option('build_name', default_value=instance.name)
        (rpm_name, template_name) = self._find_template_and_rpm_name(instance, build_name)
        try:
            egg_name = instance.egg_info['name']
            params["version"] = instance.egg_info["version"]
        except AttributeError:
            pass
        else:
            if any(s.endswith("client")
                   for s in (instance.name, egg_name, build_name)):
                client_name = utils.strip_prefix_suffix(egg_name, "python-", "client")
                if not client_name:
                    msg = "Bad client package name %s" % (egg_name)
                    raise excp.PackageException(msg)
                params["clientname"] = client_name
                params["apiname"] = instance.get_option(
                    'api_name', default_value=client_name.title())

        if all((rpm_name, template_name)):
            spec_filename = self._write_spec_file(instance, rpm_name,
                                                  template_name, params)
            self._build_from_spec(instance, spec_filename, patches)
        else:
            self.py2rpm_helper.build_srpm(source=instance.get_option("app_dir"),
                                          log_filename=instance.name,
                                          release=params.get("release"),
                                          with_tests=not params.get("no_tests"))

    def _get_rpm_names(self, from_deps=True, from_instances=True):
        desired_rpms = []
        py_reqs = set()
        if from_instances:
            inst_packages = list(self.requirements["requires"])
            for inst in self.instances:
                inst_packages.extend(inst.package_names())
                if sh.isdir(inst.get_option("app_dir")):
                    try:
                        py_req = inst.egg_info['req']
                    except AttributeError:
                        pass
                    else:
                        rpm_name, _ = self._find_template_and_rpm_name(
                            inst, inst.get_option('build_name', default_value=inst.name)
                        )
                        if rpm_name is not None:
                            desired_rpms.append((rpm_name, py_req))
                        else:
                            py_reqs.add(py_req)
            for rpm_name in inst_packages:
                desired_rpms.append((rpm_name, None))
        if from_deps:
            # This file should have all the requirements (including test ones)
            # that we need to install (and which should have been built as rpms
            # in the previous build stages).
            requires = sh.load_file(self.gathered_requires_filename).splitlines()
            for line in [line.strip() for line in requires if line.strip()]:
                py_reqs.add(pip_helper.extract_requirement(line))

        rpm_names = self.py2rpm_helper.names_to_rpm_names([req.key
                                                           for req in py_reqs])
        desired_rpms.extend((rpm_names[req.key], req) for req in py_reqs)

        def _format_name(rpm_name, py_req):
            full_name = str(rpm_name).strip()
            if py_req is not None:
                full_name += ','.join(''.join(x) for x in py_req.specs)
            return full_name

        return sorted(_format_name(rpm_name, py_req)
                      for rpm_name, py_req in desired_rpms)

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
