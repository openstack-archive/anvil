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

# pylint: disable=R0915
import datetime
import pkg_resources

from anvil import action
from anvil import colorizer
from anvil import components
from anvil import log
from anvil import shell as sh
from anvil import utils

from anvil.action import PhaseFunctors

LOG = log.getLogger(__name__)


multipip_executable = "multipip"
py2rpm_executable = "py2rpm"
force_frozen = True

OPENSTACK_DEPS_PACKAGE_NAME = "openstack-deps"

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


class PrepareAction(action.Action):
    needs_sudo = False

    def __init__(self, name, distro, root_dir, cli_opts):
        action.Action.__init__(self, name, distro, root_dir, cli_opts)

    @property
    def lookup_name(self):
        return 'install'

    def _run(self, persona, component_order, instances):
        removals = []
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Downloading %s.', colorizer.quote(i.name)),
                run=lambda i: i.download(),
                end=lambda i, result: LOG.info("Performed %s downloads.", len(result))
            ),
            component_order,
            instances,
            "download",
            *removals
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Post-download patching %s.', colorizer.quote(i.name)),
                run=lambda i: i.patch("download"),
                end=None,
            ),
            component_order,
            instances,
            "download-patch",
            *removals
            )

        requires_files = []
        for inst in instances.itervalues():
            if isinstance(inst, (components.PythonInstallComponent)):
                requires_files.extend(inst.requires_files)

        def split_lines_not_empty(text):
            return [line for line in text.split("\n") if line]

        deps_dir = sh.joinpths(self.root_dir, "deps")
        rpmbuild_dir = sh.joinpths(deps_dir, "rpmbuild")
        cache_dir = sh.joinpths(deps_dir, "cache")
        sh.mkdir(deps_dir, recurse=True)
        pip_executable = str(self.distro.get_command_config('pip'))
        multipip_cmdline = [
            multipip_executable,
            "--skip-requirements-regex",
            "python.*client",
            "--pip",
            pip_executable
        ]
        if force_frozen:
            multipip_cmdline.append("--frozen")
        cmdline = multipip_cmdline + ["-r"] + filter(sh.isfile, requires_files)

        output = sh.execute(*cmdline, ignore_exit_code=True)
        conflict_descr = output[1].strip()
        forced_keys = set()
        if conflict_descr:
            for line in conflict_descr.splitlines():
                LOG.warning(line)
                if line.endswith(": incompatible requirements"):
                    forced_keys.add(line.split(":", 1)[0].lower())
        pips_to_install = [pkg
                           for pkg in split_lines_not_empty(output[0])
                           if pkg.lower() not in OPENSTACK_PACKAGES]
        if not pips_to_install:
            LOG.error("No dependencies for OpenStack found."
                      "Something went wrong. Please check:")
            LOG.error("'%s'" % "' '".join(cmdline))
            raise RuntimeError("No dependencies for OpenStack found")

        utils.log_iterable(pips_to_install, logger=LOG,
                           header="Full known Python dependency list")
        keys_to_install = []
        for pip in pips_to_install:
            req = pkg_resources.Requirement.parse(pip)
            keys_to_install.append(req.key)
            if req.key in forced_keys:
                components.PythonInstallComponent.forced_packages.append(req)

        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Preparing %s.', colorizer.quote(i.name)),
                run=lambda i: i.prepare(),
                end=None,
            ),
            component_order,
            instances,
            "prepare",
            *removals
            )
###########################
        # TODO(aababilov): move this RHEL specific code somewhere
        cmdline = [py2rpm_executable, "--convert"] + pips_to_install
        output = sh.execute(*cmdline)

        sh.deldir(rpmbuild_dir)
        deps_repo_dir = sh.joinpths(deps_dir, "openstack-deps")
        sh.mkdir(deps_repo_dir, recurse=True)
        for filename in sh.listdir(deps_repo_dir):
            if sh.basename(filename).startswith(OPENSTACK_DEPS_PACKAGE_NAME):
                sh.unlink(filename)

        today = datetime.date.today()
        spec_content = """Name: %s
Version: %s.%s.%s
Release: 0
License: Apache 2.0
Summary: Python dependencies for OpenStack
BuildArch: noarch

# Python requirements
""" % (OPENSTACK_DEPS_PACKAGE_NAME, today.year, today.month, today.day)
        spec_content += output[0]

        packages = {}
        for inst in instances.itervalues():
            if isinstance(inst, components.PkgInstallComponent):
                for pack in inst.packages:
                    packages[pack["name"]] = pack

        if packages:
            spec_content += "\n# Additional requirements\n"
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

        spec_content += """
%description

%files
"""
        spec_filename = sh.joinpths(
            deps_dir, "%s.spec" % OPENSTACK_DEPS_PACKAGE_NAME)
        sh.write_file(spec_filename, spec_content)
        cmdline = ["rpmbuild",
                   "-ba",
                   "--define", "_topdir %s" % rpmbuild_dir,
                   spec_filename]
        LOG.info("Building %s RPM" % OPENSTACK_DEPS_PACKAGE_NAME)
        sh.execute(*cmdline)
###########################

        cmdline = multipip_cmdline + ["--ignore-installed"] + pips_to_install
        output = sh.execute(*cmdline, ignore_exit_code=True)
        pips_to_download = split_lines_not_empty(output[0])

        package_files = []
        if pips_to_download:
            download_dir = sh.joinpths(deps_dir, "download")
            # NOTE(aababilov): pip has issues with already downloaded files
            sh.deldir(download_dir)
            sh.mkdir(download_dir, recurse=True)
            cmdline = [
                pip_executable,
                "install",
                "--download",
                download_dir,
                "--download-cache",
                cache_dir,
            ] + pips_to_download
            out_filename = sh.joinpths(deps_dir, "pip-install-download.out")
            utils.log_iterable(pips_to_download, logger=LOG,
                               header="Downloading Python dependencies")
            LOG.info("You can watch progress in another terminal with")
            LOG.info("    tail -f %s" % out_filename)
            with open(out_filename, "w") as out:
                sh.execute(*cmdline, stdout_fh=out, stderrr_fh=out)
            package_files = sh.listdir(download_dir, files_only=True)

##################
        # TODO(aababilov): move this RHEL specific code somewhere
        if package_files:
            utils.log_iterable(package_files, logger=LOG,
                               header="Building RPM packages from files")
            cmdline = [
                py2rpm_executable,
                "--rpm-base",
                rpmbuild_dir,
                ] + package_files
            out_filename = sh.joinpths(deps_dir, "py2rpm.out")
            utils.log_iterable(package_files, logger=LOG,
                               header="Building RPMs for Python dependencies")
            LOG.info("You can watch progress in another terminal with")
            LOG.info("    tail -f %s" % out_filename)
            with open(out_filename, "w") as out:
                sh.execute(*cmdline, stdout_fh=out, stderrr_fh=out)

        for filename in sh.listdir(sh.joinpths(rpmbuild_dir, "RPMS"),
                                   recursive=True, files_only=True):
            new_name = sh.joinpths(deps_repo_dir, sh.basename(filename))
            if sh.isfile(new_name):
                sh.unlink(new_name)
            sh.move(filename, new_name)

        cmdline = ["createrepo", deps_repo_dir]
        LOG.info("Creating repo at %s" % deps_repo_dir)
        sh.execute(*cmdline)
        anvil_repo_filename = sh.joinpths(deps_dir, "anvil.repo")
        LOG.info("Writing anvil.repo to %s" % anvil_repo_filename)
        (_fn, content) = utils.load_template('packaging', 'anvil.repo')
        params = {"baseurl": "file://%s" % deps_repo_dir}
        sh.write_file(anvil_repo_filename, utils.expand_template(content, params))
##################
