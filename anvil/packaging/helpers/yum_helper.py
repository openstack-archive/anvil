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

import tempfile
import time

from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

LOG = logging.getLogger(__name__)


def _generate_log_filename(arglist):
    pieces = ['yyoom-']
    for a in arglist:
        a = a.strip()
        if not a or a.startswith("-") or sh.exists(a):
            break
        else:
            pieces.append(a)
            pieces.append("_")
    pieces.append(int(time.time()))
    pieces.append("_")
    pieces.append(utils.get_random_string(4))
    pieces.append('.log')
    return "".join([str(p) for p in pieces])


class Helper(object):

    def __init__(self, log_dir, repos):
        # Executables we require to operate
        self.yyoom_executable = sh.which("yyoom", ["tools/"])
        # Preferred repositories names
        self._repos = repos
        # Caches of installed and available packages
        self._installed = None
        self._available = None
        self._logs_dir = log_dir

    def _yyoom(self, arglist, on_completed=None):
        if not on_completed:
            on_completed = lambda data, errored: None
        if not sh.isdir(self._logs_dir):
            sh.mkdirslist(self._logs_dir)
        with tempfile.NamedTemporaryFile(suffix=".json") as fh:
            cmdline = [
                self.yyoom_executable,
                "--output-file", fh.name,
                "--verbose",
            ]
            cmdline.extend(arglist)
            log_filename = sh.joinpths(self._logs_dir,
                                       _generate_log_filename(arglist))
            LOG.debug("Running yyoom: log output will be placed in %s",
                      log_filename)
            try:
                sh.execute_save_output(cmdline, log_filename)
            except excp.ProcessExecutionError:
                with excp.reraise():
                    try:
                        fh.seek(0)
                        data = utils.parse_json(fh.read())
                    except Exception:
                        LOG.exception("Failed to parse YYOOM output")
                    else:
                        on_completed(data, True)
            else:
                fh.seek(0)
                data = utils.parse_json(fh.read())
                on_completed(data, False)
                return data

    def _traced_yyoom(self, arglist, tracewriter):
        def on_completed(data, errored):
            self._handle_transaction_data(tracewriter, data)
        return self._yyoom(arglist, on_completed=on_completed)

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
        except Exception:
            LOG.exception("Failed to handle YYOOM transaction data")
        else:
            if failed_names:
                raise RuntimeError("YYOOM failed on %s" % ", ".join(failed_names))

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
            self._available = self._yyoom(['list', 'available'])
        return list(self._available)

    def list_installed(self):
        if self._installed is None:
            self._installed = self._yyoom(['list', 'installed'])
        return list(self._installed)

    def builddep(self, srpm_path, tracewriter=None):
        self._traced_yyoom(['builddep', srpm_path], tracewriter)

    def _reset(self):
        # reset the caches:
        self._installed = None
        self._available = None

    def clean(self):
        try:
            self._yyoom(['cleanall'])
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
        for repo in self._repos:
            cmdline.append('--prefer-repo')
            cmdline.append(repo)

        try:
            self._traced_yyoom(cmdline, tracewriter)
        finally:
            self._reset()
