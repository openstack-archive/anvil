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

import json
import sys

from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh

LOG = logging.getLogger(__name__)


def _parse_json(value):
    """Load JSON from string

    If string is whitespace-only, returns None
    """
    value = value.strip()
    if value:
        return json.loads(value)
    else:
        return None


class Helper(object):

    def __init__(self, log_dir):
        # Executables we require to operate
        self.yyoom_executable = sh.which("yyoom", ["tools/"])
        # Executable logs will go into this directory
        self._log_dir = log_dir
        # Caches of installed and available packages
        self._installed = None
        self._available = None

    def _yyoom(self, arglist, cmd_type):
        cmdline = [self.yyoom_executable, '--verbose']
        cmdline.extend(arglist)
        out_filename = sh.joinpths(self._log_dir, "yyoom-%s.log" % (cmd_type))
        (stdout, _) = sh.execute_save_output2(cmdline,
                                              stderr_filename=out_filename)
        return _parse_json(stdout)

    def _traced_yyoom(self, arglist, cmd_type, tracewriter):
        try:
            data = self._yyoom(arglist, cmd_type)
        except excp.ProcessExecutionError:
            ex_type, ex, ex_tb = sys.exc_info()
            try:
                data = _parse_json(ex.stdout)
            except Exception as e:
                LOG.error("Failed to parse YYOOM output: %s", e)
            else:
                self._handle_transaction_data(tracewriter, data)
            raise ex_type, ex, ex_tb
        self._handle_transaction_data(tracewriter, data)

    @staticmethod
    def _handle_transaction_data(tracewriter, data):
        if not data:
            return
        failed_names = None
        try:
            if tracewriter:
                for action in data:
                    if action['action_type'] == 'install':
                        tracewriter.package_installed(action['name'])
                    elif action['action_type'] == 'upgrade':
                        tracewriter.package_upgraded(action['name'])
            failed_names = [action['name']
                            for action in data
                            if action['action_type'] == 'error']
        except Exception as e:
            LOG.error("Failed to handle transaction data: %s", e)
        else:
            if failed_names:
                raise RuntimeError("Yum failed on %s" % ", ".join(failed_names))

    def is_installed(self, name):
        matches = self.find_installed(name)
        if len(matches):
            return True
        return False

    def find_installed(self, name):
        installed = self.list_installed()
        return [item for item in installed if item['name'] == name]

    def list_available(self):
        if self._available is None:
            self._available = self._yyoom(['list', 'available'], 'list-available')
        return list(self._available)

    def list_installed(self):
        if self._installed is None:
            self._installed = self._yyoom(['list', 'installed'], 'list-installed')
        return list(self._installed)

    def builddep(self, srpm_path, tracewriter=None):
        self._traced_yyoom(['builddep', srpm_path],
                           'builddep-%s' % sh.basename(srpm_path), tracewriter)

    def _reset(self):
        # reset the caches:
        self._installed = None
        self._available = None

    def clean(self):
        try:
            self._yyoom(['cleanall'], 'cleanall')
        finally:
            self._reset()

    def transaction(self, install_pkgs=(), remove_pkgs=(), tracewriter=None):
        if not install_pkgs and not remove_pkgs:
            return

        cmdline = ['transaction']
        for pkg in install_pkgs:
            cmdline.append('--install')
            cmdline.append(pkg)
        for pkg in remove_pkgs:
            cmdline.append('--erase')
            cmdline.append(pkg)

        try:
            cmd_type = 'transaction'
            if install_pkgs:
                cmd_type += "-install"
            if remove_pkgs:
                cmd_type += "-remove"

            self._traced_yyoom(cmdline, cmd_type, tracewriter)
        finally:
            self._reset()
