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

from anvil import components as comp
from anvil import log as logging

LOG = logging.getLogger(__name__)


class OpenStackClientUninstaller(comp.PythonUninstallComponent):
    pass


class OpenStackClientInstaller(comp.PythonInstallComponent):
    def _filter_pip_requires_line(self, line):
        if line.lower().find('keystoneclient') != -1:
            return None
        if line.lower().find('novaclient') != -1:
            return None
        if line.lower().find('glanceclient') != -1:
            return None
        return line


class OpenStackClientRuntime(comp.EmptyRuntime):
    pass


class OpenStackClientTester(comp.PythonTestingComponent):
    def _use_run_tests(self):
        return False
