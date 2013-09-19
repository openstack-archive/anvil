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
from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

LOG = logging.getLogger(__name__)


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


OPENSTACK_PACKAGES = [
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
]


class DependencyHandler(object):
    """Basic class for handler of OpenStack dependencies.
    """
    MAX_PIP_DOWNLOAD_ATTEMPTS = 4
    multipip_executable = sh.which("multipip", ["tools/"])

    def __init__(self, distro, root_dir, instances, opts=None):
        self.distro = distro
        self.root_dir = root_dir
        self.instances = instances
        self.opts = opts or {}

        self.deps_dir = sh.joinpths(self.root_dir, "deps")
        self.download_dir = sh.joinpths(self.deps_dir, "download")
        self.log_dir = sh.joinpths(self.deps_dir, "output")
        self.gathered_requires_filename = sh.joinpths(
            self.deps_dir, "pip-requires")
        self.forced_requires_filename = sh.joinpths(
            self.deps_dir, "forced-requires")
        self.pip_executable = sh.which_first(['pip-python', 'pip'])
        self.pips_to_install = []
        self.forced_packages = []
        self._package_dirs = None
        self._python_names = None

        self.requirements = {}
        for key in ("build-requires", "requires", "conflicts"):
            req_set = set()
            for inst in self.instances:
                req_set |= set(pkg["name"]
                               for pkg in inst.get_option(key) or [])
            self.requirements[key] = req_set

    @property
    def python_names(self):
        if not self._python_names:
            self._python_names = self._get_python_names(self.package_dirs)
        return self._python_names

    @property
    def package_dirs(self):
        if not self._package_dirs:
            self._package_dirs = self._get_package_dirs(self.instances)
        return self._package_dirs

    @staticmethod
    def _get_package_dirs(instances):
        package_dirs = []
        for inst in instances:
            app_dir = inst.get_option("app_dir")
            if sh.isfile(sh.joinpths(app_dir, "setup.py")):
                package_dirs.append(app_dir)
        return package_dirs

    @staticmethod
    def _get_python_names(package_dirs):
        python_names = []
        for pkg_dir in package_dirs:
            cmdline = ["python", "setup.py", "--name"]
            python_names.append(sh.execute(cmdline, cwd=pkg_dir)[0].
                                splitlines()[-1].strip())
        return python_names

    def package_start(self):
        requires_files = []
        extra_pips = []
        for inst in self.instances:
            try:
                requires_files.extend(inst.requires_files)
            except AttributeError:
                pass
            for pkg in inst.get_option("pips") or []:
                extra_pips.append(
                    "%s%s" % (pkg["name"], pkg.get("version", "")))
        requires_files = filter(sh.isfile, requires_files)
        self.gather_pips_to_install(requires_files, extra_pips)
        self.clean_pip_requires(requires_files)

    def package_instance(self, instance):
        pass

    def package_finish(self):
        sh.remove_pip_build_dir()

    def post_bootstrap(self):
        pass

    def build_binary(self):
        pass

    def install(self):
        pass

    def uninstall(self):
        pass

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
                           header="Full known Python dependency list")
        self.forced_packages = []
        for pip in self.pips_to_install:
            req = pkg_resources.Requirement.parse(pip)
            if req.key in forced_keys:
                self.forced_packages.append(req)
        sh.write_file(self.forced_requires_filename,
                      "\n".join(str(req) for req in self.forced_packages))

    def filter_download_requires(self):
        return self.pips_to_install

    def download_dependencies(self, clear_cache=False):
        """Download dependencies from `$deps_dir/download-requires`.

        :param clear_cache: clear `$deps_dir/cache` dir (pip can work incorrectly
            when it has a cache)
        """
        sh.deldir(self.download_dir)
        sh.mkdir(self.download_dir, recurse=True)

        download_requires_filename = sh.joinpths(
            self.deps_dir, "download-requires")
        pips_to_download = self.filter_download_requires()
        sh.write_file(download_requires_filename,
                      "\n".join(str(req) for req in pips_to_download))
        if not pips_to_download:
            return []
        pip_dir = sh.joinpths(self.deps_dir, "pip")
        pip_download_dir = sh.joinpths(pip_dir, "download")
        pip_build_dir = sh.joinpths(pip_dir, "build")
        pip_cache_dir = sh.joinpths(pip_dir, "cache")
        if clear_cache:
            sh.deldir(pip_cache_dir)
        pip_ok = False
        for attempt in xrange(self.MAX_PIP_DOWNLOAD_ATTEMPTS):
            # NOTE(aababilov): pip has issues with already downloaded files
            sh.deldir(pip_download_dir)
            sh.mkdir(pip_download_dir, recurse=True)
            sh.deldir(pip_build_dir)
            cmdline = [
                self.pip_executable,
                "install",
                "--download", pip_download_dir,
                "--download-cache", pip_cache_dir,
                "--build", pip_build_dir,
                "-r",
                download_requires_filename,
            ]
            utils.log_iterable(
                sorted(pips_to_download),
                logger=LOG,
                header="Downloading Python dependencies (attempt %s)" %
                attempt)
            out_filename = sh.joinpths(
                self.log_dir, "pip-download-attempt-%s.out" % attempt)
            try:
                sh.execute_save_output(cmdline, out_filename=out_filename)
            except:
                LOG.info("pip failed")
            else:
                pip_ok = True
            for filename in sh.listdir(pip_download_dir, files_only=True):
                sh.move(filename, self.download_dir, force=True)
            if pip_ok:
                break
        if not pip_ok:
            raise excp.DownloadException(
                "pip downloading failed after %s attempts" %
                self.MAX_PIP_DOWNLOAD_ATTEMPTS)
        return sh.listdir(self.download_dir, files_only=True)
