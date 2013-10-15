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

from anvil import log as logging
from anvil import shell as sh
from anvil import settings
from anvil import utils

LOG = logging.getLogger(__name__)


class Helper(object):
    OPENSTACK_EPOCH = 2

    def __init__(self, python_names, package_map, arch_dependent,
                 rpmbuild_dir, download_dir, deps_dir, log_dir):
        self._py2rpm_executable = sh.which("py2rpm", ["tools/"])
        self._python_names = python_names
        self._package_map = package_map
        self._arch_dependent = arch_dependent
        # Various paths that are used during operating
        self._rpmbuild_dir = rpmbuild_dir
        self._download_dir = download_dir
        self._deps_dir = deps_dir
        self._log_dir = log_dir

    def _start_cmdline(self):
        cmdline = [
            self._py2rpm_executable,
            "--rpm-base",
            self._rpmbuild_dir
        ]
        if self._python_names:
            cmdline += [
                "--epoch-map"
            ] + ["%s==%s" % (name, self.OPENSTACK_EPOCH)
                 for name in self._python_names]
        if self._package_map:
            cmdline += [
                "--package-map",
            ] + ["%s==%s" % (key, value)
                 for key, value in self._package_map.iteritems()]
        if self._arch_dependent:
            cmdline += [
                "--arch-dependent",
            ] + list(self._arch_dependent)
        return cmdline

    def execute_make(self, filename, marks_dir, jobs):
        cmdline = ["make", "-f", filename, "-j", str(jobs)]
        out_filename = sh.joinpths(self._log_dir, "%s.log" % sh.basename(filename))
        sh.execute_save_output(cmdline, cwd=marks_dir, out_filename=out_filename)

    def convert_names_to_rpm(self, python_names, only_name=True):
        if not python_names:
            return []
        cmdline = self._start_cmdline() + ["--convert"] + python_names
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

    def build_srpm(self, package_files, tracewriter, jobs):
        (_fn, content) = utils.load_template(sh.joinpths("packaging", "makefiles"), "source.mk")
        scripts_dir = sh.abspth(sh.joinpths(settings.TEMPLATE_DIR, "packaging", "scripts"))
        cmdline = self._start_cmdline()[1:] + [
            "--scripts-dir", scripts_dir,
            "--source-only",
            "--rpm-base", self._rpmbuild_dir
        ]
        params = {
            "DOWNLOADS_DIR": self._download_dir,
            "LOGS_DIR": self._log_dir,
            "PY2RPM": self._py2rpm_executable,
            "PY2RPM_FLAGS": " ".join(cmdline)
        }
        marks_dir = sh.joinpths(self._deps_dir, "marks-deps")
        if not sh.isdir(marks_dir):
            sh.mkdirslist(marks_dir, tracewriter=tracewriter)
        makefile_path = sh.joinpths(self._deps_dir, "deps.mk")
        sh.write_file(makefile_path, utils.expand_template(content, params),
                      tracewriter=tracewriter)
        utils.log_iterable(package_files,
                           header="Building %s SRPM packages using %s jobs" %
                                  (len(package_files), jobs),
                           logger=LOG)
        self.execute_make(makefile_path, marks_dir, jobs)

    def build_from_app_dir(self, instance_name, app_dir, release=None):
        cmdline = self._start_cmdline() + ["--source-only"]
        if release is not None:
            cmdline.extend(["--release", release])
        cmdline.extend(["--", app_dir])
        out_filename = sh.joinpths(self._log_dir,
                                   "py2rpm-build-%s.log" % (instance_name))
        sh.execute_save_output(cmdline, cwd=app_dir, out_filename=out_filename)
