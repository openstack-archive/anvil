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

from anvil import component as comp
from anvil import log as logging

LOG = logging.getLogger(__name__)


class QpidUninstaller(comp.PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgUninstallComponent.__init__(self, *args, **kargs)


class QpidInstaller(comp.PkgInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgInstallComponent.__init__(self, *args, **kargs)


class QpidRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, *args, **kargs)
