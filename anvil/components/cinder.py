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

import copy
import io
import yaml

from anvil import cfg
from anvil import colorizer
from anvil import component as comp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils


class CinderMixin(object):

    @property
    def valid_subsystems(self):
        return set(['sch', 'api', 'vol'])


class CinderUninstaller(CinderMixin, comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)


class CinderInstaller(CinderMixin, comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)

    def _filter_pip_requires_line(self, line):
        if line.lower().find('glance') != -1:
            return None
        return line


class CinderRuntime(CinderMixin, comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, *args, **kargs)
