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

from Util import (component_pths)

"""
An abstraction that different components
can inherit from to perform or basic install
and configure and uninstall actions.
"""


class ComponentBase():
    def __init__(self, component_name, *args, **kargs):
        self.cfg = kargs.get("cfg")
        self.packager = kargs.get("pkg")
        self.distro = kargs.get("distro")
        self.root = kargs.get("root")
        self.othercomponents = set(kargs.get("components"))
        pths = component_pths(self.root, component_name)
        self.componentroot = pths.get('root_dir')
        self.tracedir = pths.get("trace_dir")
        self.appdir = pths.get("app_dir")
        self.cfgdir = pths.get('config_dir')

#
#the following are just interfaces...
#


class InstallComponent():
    def download(self):
        raise NotImplementedError()

    def configure(self):
        raise NotImplementedError()

    def install(self):
        raise NotImplementedError()


class UninstallComponent():
    def unconfigure(self):
        raise NotImplementedError()

    def uninstall(self):
        raise NotImplementedError()


class RuntimeComponent():
    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def status(self):
        raise NotImplementedError()

    def restart(self):
        raise NotImplementedError()
