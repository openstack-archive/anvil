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


import Logger
from Component import (ComponentBase, RuntimeComponent,
                       UninstallComponent, InstallComponent)

LOG = Logger.getLogger("install.horizon")


class HorizonTraceWriter():
    def __init__(self, root):
        pass


class HorizonTraceReader():
    def __init__(self, root):
        pass


class HorizonUninstaller(UninstallComponent):
    def __init__(self, *args, **kargs):
        pass


class HorizonInstaller(InstallComponent):
    def __init__(self, *args, **kargs):
        pass


class HorizonRuntime(RuntimeComponent):
    def __init__(self, *args, **kargs):
        pass
