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

import sys
import json

from anvil import log as logging
from anvil import shell as sh

LOG = logging.getLogger(__name__)


class Helper(object):

    def __init__(self):
        self._installed = None
        self._available = None

    @staticmethod
    def _yyoom(arglist):
        executable = sh.which("yyoom", ["tools/"])
        cmdline = [executable]
        if LOG.logger.isEnabledFor(logging.DEBUG):
            cmdline.append('--verbose')
        cmdline.extend(arglist)
        out = sh.execute(cmdline, stderr_fh=sys.stderr)[0].strip()
        if out:
            return json.loads(out)
        return None

    @staticmethod
    def _trace_installed_packages(tracewriter, data):
        if tracewriter is None or not data:
            return
        for action in data:
            if action['action_type'] == 'install':
                tracewriter.package_installed(action['name'])

    def is_installed(self, name):
        if len(self.get_installed(name)):
            return True
        else:
            return False

    def get_available(self):
        if self._available is None:
            self._available = self._yyoom(['list', 'available'])
        return self._available

    def get_installed(self, name):
        if self._installed is None:
            self._installed = self._yyoom(['list', 'installed'])
        return [item for item in self._installed
                if item['name'] == name]

    def builddep(self, srpm_path, tracewriter=None):
        data = self._yyoom(['builddep', srpm_path])
        self._trace_installed_packages(tracewriter, data)

    def clean(self):
        self._yyoom(['cleanall'])

    def transaction(self, install_pkgs=(), remove_pkgs=(), tracewriter=None):
        if not install_pkgs and not remove_pkgs:
            return

        # reset the caches:
        self._installed = None
        self._available = None

        cmdline = ['transaction']
        for pkg in install_pkgs:
            cmdline.append('--install')
            cmdline.append(pkg)
        for pkg in remove_pkgs:
            cmdline.append('--erase')
            cmdline.append(pkg)

        data = self._yyoom(cmdline)
        self._trace_installed_packages(tracewriter, data)
