# vim: tabstop=4 shiftwidth=4 softtabstop=4

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


from devstack import component as comp
from devstack import constants
from devstack import log as logging
from devstack import shell as sh
from devstack import utils

LOG = logging.getLogger("devstack.components.swift")


class SwiftUninstaller(comp.UninstallComponent):
    def __init__(self, *args, **kargs):
        pass


class SwiftInstaller(comp.InstallComponent):
    def __init__(self, *args, **kargs):
        pass


class SwiftRuntime(comp.RuntimeComponent):
    def __init__(self, *args, **kargs):
        pass
