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

import pkg_resources

from anvil import colorizer
from anvil import env
from anvil import exceptions as exc
from anvil import log as logging
from anvil.packaging.helpers import pip_helper
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils

LOG = logging.getLogger(__name__)

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


class InstallHelper(object):
    """Run pre and post install for a single package.
    """
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
    """Basic class for handler of OpenStack dependencies.
    """
    MAX_PIP_DOWNLOAD_ATTEMPTS = 4
    multipip_executable = sh.which("multipip", ["tools/"])

    def __init__(self, distro, root_dir, instances):
        self.distro = distro
        self.root_dir = root_dir
        self.instances = instances
        self.deps_dir = sh.joinpths(self.root_dir, "deps")
        self.download_dir = sh.joinpths(self.deps_dir, "download")
        self.log_dir = sh.joinpths(self.deps_dir, "output")
        self.gathered_requires_filename = sh.joinpths(
            self.deps_dir, "pip-requires")
        self.forced_requires_filename = sh.joinpths(
            self.deps_dir, "forced-requires")
        self.pip_executable = str(self.distro.get_command_config('pip'))
        self.pips_to_install = []
        self.forced_packages = []
        # These packages conflict with our deps and must be removed
        self.nopackages = env.get_key('CONFLICTING_PACKAGES', '').split()
        self.package_dirs = self._get_package_dirs(instances)
        # Instantiate this as late as we can.
        self._python_names = None
        # Track what file we create so they can be cleaned up on uninstall.
        trace_fn = tr.trace_filename(self.root_dir, 'deps')
        self.tracewriter = tr.TraceWriter(trace_fn, break_if_there=False)
        self.tracereader = tr.TraceReader(trace_fn)

    @property
    def python_names(self):
        if self._python_names is None:
            names = []
            for i in self.instances:
                try:
                    names.append(i.egg_info['name'])
                except AttributeError:
                    pass
            self._python_names = names
        return self._python_names

    @staticmethod
    def _get_package_dirs(instances):
        package_dirs = []
        for inst in instances:
            app_dir = inst.get_option("app_dir")
            if sh.isfile(sh.joinpths(app_dir, "setup.py")):
                package_dirs.append(app_dir)
        return package_dirs

    def package_start(self):
        requires_files = []
        extra_pips = []
        for i in self.instances:
            try:
                requires_files.extend(i.requires_files)
            except AttributeError:
                pass
            # Ensure we include any extra pips that are desired.
            i_extra_pips = i.get_option("pips") or []
            for i_pip in i_extra_pips:
                extra_req = pip_helper.create_requirement(i_pip['name'],
                                                          i_pip.get('version'))
                extra_pips.append(str(extra_req))
        requires_files = filter(sh.isfile, requires_files)
        self.gather_pips_to_install(requires_files, sorted(set(extra_pips)))
        self.clean_pip_requires(requires_files)

    def package_instance(self, instance):
        pass

    def package_finish(self):
        pass

    def install(self):
        for inst in self.instances:
            for pkg in inst.get_option("nopackages") or []:
                if pkg['name'] not in self.nopackages:
                    self.nopackages.append(pkg["name"])

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
            self.tracereader = None

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
                    req = pip_helper.extract_requirement(line)
                    new_lines.append(str(forced_by_key[req.key]))
                except:
                    # we don't force the package or it has a bad format
                    new_lines.append(line)
            contents = "# Cleaned on %s\n\n%s\n" % (
                utils.iso8601(), "\n".join(new_lines))
            sh.write_file_and_backup(fn, contents)

    def gather_pips_to_install(self, requires_files, extra_pips=None):
        """Analyze requires_files and extra_pips.

        Updates `self.forced_packages` and `self.pips_to_install`.
        Writes requirements to `self.gathered_requires_filename`.
        """
        extra_pips = extra_pips or []
        cmdline = [
            self.multipip_executable,
            "--skip-requirements-regex",
            "python.*client",
            "--pip",
            self.pip_executable
        ]
        cmdline = cmdline + extra_pips + ["-r"] + requires_files
        cmdline = (cmdline + ["--ignore-package"] +
                   OPENSTACK_PACKAGES + self.python_names)

        output = sh.execute(cmdline, check_exit_code=False)
        self.pips_to_install = list(utils.splitlines_not_empty(output[0]))
        conflict_descr = output[1].strip()

        forced_keys = set()
        if conflict_descr:
            for line in conflict_descr.splitlines():
                LOG.warning(line)
                if line.endswith(": incompatible requirements"):
                    forced_keys.add(line.split(":", 1)[0].lower())

        sh.write_file(self.gathered_requires_filename,
                      "\n".join(self.pips_to_install))

        if not self.pips_to_install:
            LOG.error("No dependencies for OpenStack found."
                      "Something went wrong. Please check:")
            LOG.error("'%s'" % "' '".join(cmdline))
            raise RuntimeError("No dependencies for OpenStack found")

        utils.log_iterable(sorted(self.pips_to_install),
                           logger=LOG,
                           header="Full known python dependency list")
        self.forced_packages = []
        for line in self.pips_to_install:
            req = pip_helper.extract_requirement(line)
            if req.key in forced_keys:
                self.forced_packages.append(req)
        sh.write_file(self.forced_requires_filename,
                      "\n".join(str(req) for req in self.forced_packages))

    def filter_download_requires(self):
        return self.pips_to_install

    def _try_download_dependencies(self, attempt, pips_to_download,
                                   pip_download_dir,
                                   pip_cache_dir,
                                   pip_build_dir):
        pips_to_download = [str(p) for p in pips_to_download]
        cmdline = [
            self.pip_executable,
            "install",
            "--download", pip_download_dir,
            "--download-cache", pip_cache_dir,
            "--build", pip_build_dir,
        ]
        cmdline.extend(sorted(pips_to_download))
        download_filename = "pip-download-attempt-%s.out"
        download_filename = download_filename % (attempt)
        out_filename = sh.joinpths(self.log_dir, download_filename)
        sh.execute_save_output(cmdline, out_filename=out_filename)

    def _examine_download_dir(self, pips_to_download, pip_download_dir):
        pip_names = set([p.key for p in pips_to_download])
        what_downloaded = sh.listdir(pip_download_dir, files_only=True)
        LOG.info("Validating %s files that were downloaded.",
                 len(what_downloaded))
        for filename in what_downloaded:
            pkg_details = pip_helper.get_archive_details(filename)
            req = pkg_details['req']
            if req.key not in pip_names:
                LOG.info("Dependency %s was automatically included.",
                         colorizer.quote(req))

    def download_dependencies(self, clear_cache=False):
        """Download dependencies from `$deps_dir/download-requires`.

        :param clear_cache: clear `$deps_dir/cache` dir (pip can work incorrectly
            when it has a cache)
        """
        sh.deldir(self.download_dir)
        sh.mkdirslist(self.download_dir, tracewriter=self.tracewriter)
        download_requires_filename = sh.joinpths(self.deps_dir,
                                                 "download-requires")
        raw_pips_to_download = self.filter_download_requires()
        sh.write_file(download_requires_filename,
                      "\n".join(str(req) for req in raw_pips_to_download))
        if not raw_pips_to_download:
            return ([], [])
        pip_dir = sh.joinpths(self.deps_dir, "pip")
        pip_download_dir = sh.joinpths(pip_dir, "download")
        pip_build_dir = sh.joinpths(pip_dir, "build")
        pip_cache_dir = sh.joinpths(pip_dir, "cache")
        if clear_cache:
            sh.deldir(pip_cache_dir)
        pip_failures = []
        for attempt in xrange(self.MAX_PIP_DOWNLOAD_ATTEMPTS):
            # NOTE(aababilov): pip has issues with already downloaded files
            sh.deldir(pip_download_dir)
            sh.mkdir(pip_download_dir, recurse=True)
            sh.deldir(pip_build_dir)
            header = "Downloading %s python dependencies (attempt %s)"
            header = header % (len(raw_pips_to_download), attempt)
            utils.log_iterable(sorted(raw_pips_to_download),
                               logger=LOG,
                               header=header)
            failed = False
            try:
                self._try_download_dependencies(attempt, raw_pips_to_download,
                                                pip_download_dir,
                                                pip_cache_dir, pip_build_dir)
                pip_failures = []
            except exc.ProcessExecutionError as e:
                LOG.exception("Failed downloading python dependencies")
                pip_failures.append(e)
                failed = True
            if not failed:
                break
        if pip_failures:
            raise pip_failures[-1]
        pips_downloaded = [pip_helper.extract_requirement(p)
                           for p in raw_pips_to_download]
        self._examine_download_dir(pips_downloaded, pip_download_dir)
        for filename in sh.listdir(pip_download_dir, files_only=True):
            sh.move(filename, self.download_dir)
        what_downloaded = sh.listdir(self.download_dir, files_only=True)
        return (pips_downloaded, what_downloaded)
