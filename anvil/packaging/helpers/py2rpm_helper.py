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

    def __init__(self, dependency_handler):
        self._py2rpm_executable = sh.which("py2rpm", ["tools/"])
        self._dh = dependency_handler

    def _start_cmdline(self): # _py2rpm_start_cmdline
        cmdline = [
            self._py2rpm_executable,
            "--rpm-base",
            self._dh.rpmbuild_dir
        ]
        if self._dh.python_names:
            cmdline += [
                "--epoch-map"
            ] + ["%s==%s" % (name, self._dh.OPENSTACK_EPOCH)
                 for name in self._dh.python_names]
        package_map = self._dh.distro.get_dependency_config("package_map")
        if package_map:
            cmdline += [
                "--package-map",
            ] + ["%s==%s" % (key, value)
                 for key, value in package_map.iteritems()]
        arch_dependent = self._dh.distro.get_dependency_config("arch_dependent")
        if arch_dependent:
            cmdline += [
                "--arch-dependent",
            ] + list(arch_dependent)
        return cmdline

    def _execute_make(self, filename, marks_dir):
        cmdline = ["make", "-f", filename, "-j", str(self._dh._jobs)]
        out_filename = sh.joinpths(self._dh.log_dir, "%s.log" % sh.basename(filename))
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

    def build_srpm(self, package_files):
        (_fn, content) = utils.load_template(sh.joinpths("packaging", "makefiles"), "source.mk")
        scripts_dir = sh.abspth(sh.joinpths(settings.TEMPLATE_DIR, "packaging", "scripts"))
        cmdline = self._start_cmdline()[1:] + [
            "--scripts-dir", scripts_dir,
            "--source-only",
            "--rpm-base", self._dh.rpmbuild_dir
        ]
        params = {
            "DOWNLOADS_DIR": self._dh.download_dir,
            "LOGS_DIR": self._dh.log_dir,
            "PY2RPM": self._py2rpm_executable,
            "PY2RPM_FLAGS": " ".join(cmdline)
        }
        marks_dir = sh.joinpths(self._dh.deps_dir, "marks-deps")
        if not sh.isdir(marks_dir):
            sh.mkdirslist(marks_dir, tracewriter=self._dh.tracewriter)
        makefile_path = sh.joinpths(self._dh.deps_dir, "deps.mk")
        sh.write_file(makefile_path, utils.expand_template(content, params),
                      tracewriter=self._dh.tracewriter)
        utils.log_iterable(package_files,
                           header="Building %s SRPM packages using %s jobs" % (len(package_files), self._jobs),
                           logger=LOG)
        self._execute_make(makefile_path, marks_dir)
