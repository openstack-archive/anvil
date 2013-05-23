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
from anvil.packaging import base
from anvil import shell as sh
from anvil import trace as tr


LOG = logging.getLogger(__name__)

py2rpm_executable = "py2rpm"


class PythonPackager(base.EmptyPackager):
    def __init__(self, *args, **kwargs):
        super(PythonPackager, self).__init__(*args, **kwargs)
        self.tracewriter = tr.TraceWriter(
            tr.trace_filename(self.get_option('trace_dir'), 'created'),
            break_if_there=False)
        self.package_dir = sh.joinpths(self.get_option('component_dir'), 'package')

        if sh.isdir(self.package_dir):
            sh.deldir(self.package_dir)
        sh.mkdir(self.package_dir, recurse=True)

    def package(self):
        cmdline = [
            py2rpm_executable,
            "--rpm-base",
            self.package_dir,
        ]
        out_fn = sh.joinpths(self.get_option('trace_dir'),
                                "%s.py2rpm" % (self.name))
        sh.execute(
            *cmdline,
            cwd=self.get_option('app_dir'),
            stderr_fn='%s.stderr' % (out_fn),
            stdout_fn='%s.stdout' % (out_fn),
            tracewriter=self.tracewriter)
        return self.package_dir
