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

# R0902: Too many instance attributes
# R0921: Abstract class not referenced
#pylint: disable=R0902,R0921

import collections

from anvil import colorizer
from anvil import decorators
from anvil import exceptions as exc
from anvil import log as logging
from anvil.packaging.helpers import pip_helper
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils

LOG = logging.getLogger(__name__)


class InstallHelper(object):
    """Run pre and post install for a single package."""
    def __init__(self, distro):
        self.distro = distro

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


class DependencyHandler(object):
    """Basic class for handler of OpenStack dependencies."""
    MAX_PIP_DOWNLOAD_ATTEMPTS = 4
    PIP_DOWNLOAD_DELAY = 10

    def __init__(self, distro, root_dir, instances, opts):
        self.distro = distro
        self.root_dir = root_dir
        self.instances = instances
        self.opts = opts or {}
        # Various paths we will use while operating
        self.deps_dir = sh.joinpths(self.root_dir, "deps")
        self.downloaded_flag_file = sh.joinpths(self.deps_dir, "pip-downloaded")
        self.download_dir = sh.joinpths(self.deps_dir, "download")
        self.log_dir = sh.joinpths(self.deps_dir, "output")
        sh.mkdir(self.log_dir, recurse=True)
        self.gathered_requires_filename = sh.joinpths(self.deps_dir, "pip-requires")
        self.forced_requires_filename = sh.joinpths(self.deps_dir, "forced-requires")
        self.download_requires_filename = sh.joinpths(self.deps_dir, "download-requires")
        # Executables we require to operate
        self.multipip_executable = sh.which("multipip", ["tools/"])
        # List of requirements
        self.pips_to_install = []
        self.forced_packages = []
        # Instances to there app directory (with a setup.py inside)
        self.package_dirs = self._get_package_dirs(instances)
        # Track what file we create so they can be cleaned up on uninstall.
        trace_fn = tr.trace_filename(self.root_dir, 'deps')
        self.tracewriter = tr.TraceWriter(trace_fn, break_if_there=False)
        self.tracereader = tr.TraceReader(trace_fn)
        self.requirements = {}
        for key in ("build-requires", "requires", "conflicts"):
            req_set = set()
            for inst in self.instances:
                req_set |= set(pkg["name"]
                               for pkg in inst.get_option(key) or [])
            self.requirements[key] = req_set
        # These pip names we will ignore from being converted/analyzed...
        ignore_pips = self.distro.get_dependency_config("ignoreable_pips", quiet=True)
        if not ignore_pips:
            self.ignore_pips = set()
        else:
            self.ignore_pips = set(ignore_pips)

    @decorators.cached_property(ttl=0)
    def _python_eggs(self):
        egg_infos = []
        for i in self.instances:
            try:
                egg_infos.append(dict(i.egg_info))
            except AttributeError:
                pass
        return egg_infos

    @property
    def python_names(self):
        return [e['name'] for e in self._python_eggs]

    @staticmethod
    def _get_package_dirs(instances):
        package_dirs = []
        for inst in instances:
            app_dir = inst.get_option("app_dir")
            if sh.isfile(sh.joinpths(app_dir, "setup.py")):
                package_dirs.append(app_dir)
        return package_dirs

    def package_start(self):
        create_requirement = pip_helper.create_requirement

        def gather_extras(instance):
            pips = []
            for p in instance.get_option("pips", default_value=[]):
                req = create_requirement(p['name'], p.get('version'))
                pips.append(str(req))
            requires_files = list(getattr(instance, 'requires_files', []))
            if instance.get_bool_option('use_tests_requires', default_value=True):
                requires_files.extend(getattr(instance, 'test_requires_files', []))
            return (pips, requires_files)

        requires_files = []
        extra_pips = []
        for i in self.instances:
            instance_pips, instance_requires_files = gather_extras(i)
            extra_pips.extend(instance_pips)
            requires_files.extend(instance_requires_files)
        requires_files = filter(sh.isfile, requires_files)
        self._gather_pips_to_install(requires_files, sorted(set(extra_pips)))
        self._clean_pip_requires(requires_files)

    def package_instance(self, instance):
        pass

    def package_finish(self):
        pass

    def build_binary(self):
        pass

    def install(self, general):
        pass

    def install_all_deps(self):
        pass

    def uninstall(self):
        pass

    def destroy(self):
        self.uninstall()
        # Clear out any files touched.
        if self.tracereader.exists():
            for f in self.tracereader.files_touched():
                sh.unlink(f)
            for d in self.tracereader.dirs_made():
                sh.deldir(d)
            sh.unlink(self.tracereader.filename())

    def _clean_pip_requires(self, requires_files):
        # Fixup incompatible dependencies
        if not (requires_files and self.forced_packages):
            return
        utils.log_iterable(sorted(requires_files),
                           logger=LOG,
                           header="Adjusting %s pip 'requires' files" % (len(requires_files)))
        forced_by_key = dict((pkg.key, pkg) for pkg in self.forced_packages)
        for fn in requires_files:
            old_lines = sh.load_file(fn).splitlines()
            new_lines = []
            for line in old_lines:
                try:
                    req = pip_helper.extract_requirement(line)
                    new_lines.append(str(forced_by_key[req.key]))
                except Exception:
                    # we don't force the package or it has a bad format
                    new_lines.append(line)
            contents = "# Cleaned on %s\n\n%s\n" % (utils.iso8601(), "\n".join(new_lines))
            sh.write_file_and_backup(fn, contents)
        # NOTE(imelnikov): after updating requirement lists we should re-fetch
        # data from them again, so we drop pip helper caches here.
        pip_helper.drop_caches()

    def _gather_pips_to_install(self, requires_files, extra_pips=None):
        """Analyze requires_files and extra_pips.

        Updates `self.forced_packages` and `self.pips_to_install`.
        Writes requirements to `self.gathered_requires_filename`.
        """
        extra_pips = extra_pips or []
        cmdline = [self.multipip_executable]
        cmdline = cmdline + extra_pips + ["-r"] + requires_files

        ignore_pip_names = set(self.python_names)
        ignore_pip_names.update(self.ignore_pips)
        if ignore_pip_names:
            cmdline.extend(["--ignore-package"])
            cmdline.extend(ignore_pip_names)

        stdout, stderr = sh.execute(cmdline, check_exit_code=False)
        self.pips_to_install = list(utils.splitlines_not_empty(stdout))
        sh.write_file(self.gathered_requires_filename, "\n".join(self.pips_to_install))
        utils.log_iterable(sorted(self.pips_to_install), logger=LOG,
                           header="Full known python dependency list")

        incompatibles = collections.defaultdict(list)
        if stderr:
            current_name = ''
            for line in stderr.strip().splitlines():
                if line.endswith(": incompatible requirements"):
                    current_name = line.split(":", 1)[0].lower().strip()
                    if current_name not in incompatibles:
                        incompatibles[current_name] = []
                else:
                    incompatibles[current_name].append(line)
            for (name, lines) in incompatibles.items():
                if not name:
                    continue
                LOG.warn("Incompatible requirements found for %s",
                         colorizer.quote(name, quote_color='red'))
                for line in lines:
                    LOG.warn(line)

        if not self.pips_to_install:
            LOG.error("No dependencies for OpenStack found."
                      "Something went wrong. Please check:")
            LOG.error("'%s'" % "' '".join(cmdline))
            raise exc.DependencyException("No dependencies for OpenStack found")

        # Translate those that we altered requirements for into a set of forced
        # requirements file (and associated list).
        self.forced_packages = [e['req'] for e in self._python_eggs]
        forced_packages_keys = [e.key for e in self.forced_packages]
        for req in [pip_helper.extract_requirement(line) for line in self.pips_to_install]:
            if req.key in incompatibles:
                if req.key not in forced_packages_keys:
                    self.forced_packages.append(req)
                    forced_packages_keys.append(req.key)
        self.forced_packages = list(sorted(self.forced_packages))
        forced_packages = [str(req) for req in self.forced_packages]
        utils.log_iterable(forced_packages, logger=LOG,
                           header="Forced python dependencies")
        sh.write_file(self.forced_requires_filename, "\n".join(forced_packages))

    def _filter_download_requires(self):
        """Shrinks the pips that were downloaded into a smaller set.

        :returns: a list of all requirements that must be downloaded
        :rtype: list of str
        """
        return self.pips_to_install

    def _examine_download_dir(self, pips_to_download, pip_download_dir):
        pip_names = set([p.key for p in pips_to_download])
        what_downloaded = sorted(sh.listdir(pip_download_dir, files_only=True))
        LOG.info("Validating %s files that were downloaded.", len(what_downloaded))
        for filename in what_downloaded:
            pkg_details = pip_helper.get_archive_details(filename)
            req = pkg_details['req']
            if req.key not in pip_names:
                LOG.info("Dependency %s was automatically included.",
                         colorizer.quote(req))
        return what_downloaded

    @staticmethod
    def _requirements_satisfied(pips_list, download_dir):
        downloaded_req = [pip_helper.get_archive_details(filename)["req"]
                          for filename in sh.listdir(download_dir, files_only=True)]
        downloaded_req = dict((req.key, req.specs[0][1]) for req in downloaded_req)
        for req_str in pips_list:
            req = pip_helper.extract_requirement(req_str)
            try:
                downloaded_version = downloaded_req[req.key]
            except KeyError:
                return False
            else:
                if downloaded_version not in req:
                    return False
        return True

    def download_dependencies(self):
        """Download dependencies from `$deps_dir/download-requires`."""
        # NOTE(aababilov): do not drop download_dir - it can be reused
        sh.mkdirslist(self.download_dir, tracewriter=self.tracewriter)
        pips_to_download = self._filter_download_requires()
        sh.write_file(self.download_requires_filename,
                      "\n".join([str(req) for req in pips_to_download]))
        if not pips_to_download:
            return ([], [])
        # NOTE(aababilov): user could have changed persona, so,
        # check that all requirements are downloaded
        if (sh.isfile(self.downloaded_flag_file) and
                self._requirements_satisfied(pips_to_download, self.download_dir)):
            LOG.info("All python dependencies have been already downloaded")
        else:
            def try_download(attempt):
                LOG.info("Downloading %s dependencies with pip (attempt %s)...",
                         len(pips_to_download), attempt)
                output_filename = sh.joinpths(self.log_dir,
                                              "pip-download-attempt-%s.log" % (attempt))
                pip_helper.download_dependencies(self.download_dir,
                                                 pips_to_download,
                                                 output_filename)
            utils.retry(self.MAX_PIP_DOWNLOAD_ATTEMPTS,
                        self.PIP_DOWNLOAD_DELAY, try_download)
            # NOTE(harlowja): Mark that we completed downloading successfully
            sh.touch_file(self.downloaded_flag_file, die_if_there=False,
                          quiet=True, tracewriter=self.tracewriter)
        pips_downloaded = [pip_helper.extract_requirement(p) for p in pips_to_download]
        what_downloaded = self._examine_download_dir(pips_downloaded, self.download_dir)
        return (pips_downloaded, what_downloaded)
