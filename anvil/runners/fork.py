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

from anvil import exceptions as excp
from anvil import log as logging
from anvil import runners as base
from anvil import shell as sh
from anvil import trace as tr

from anvil.components import (STATUS_STARTED, STATUS_UNKNOWN)

LOG = logging.getLogger(__name__)


# Trace constants
PID_FN = "PID_FN"
STDOUT_FN = "STDOUT_FN"
STDERR_FN = "STDERR_FN"
ARGS = "ARGS"
NAME = "NAME"
FORK_TEMPL = "%s.fork"


class ForkRunner(base.Runner):
    def stop(self, app_name):
        trace_dir = self.runtime.get_option('trace_dir')
        if not sh.isdir(trace_dir):
            msg = "No trace directory found from which to stop: %s" % (app_name)
            raise excp.StopException(msg)
        with sh.Rooted(True):
            fn_name = FORK_TEMPL % (app_name)
            (pid_file, stderr_fn, stdout_fn) = self._form_file_names(fn_name)
            pid = self._extract_pid(pid_file)
            if not pid:
                msg = "Could not extract a valid pid from %s" % (pid_file)
                raise excp.StopException(msg)
            (killed, attempts) = sh.kill(pid)
            # Trash the files if it worked
            if killed:
                LOG.debug("Killed pid %s after %s attempts." % (pid, attempts))
                LOG.debug("Removing pid file %s" % (pid_file))
                sh.unlink(pid_file)
                LOG.debug("Removing stderr file %r" % (stderr_fn))
                sh.unlink(stderr_fn)
                LOG.debug("Removing stdout file %r" % (stdout_fn))
                sh.unlink(stdout_fn)
                trace_fn = tr.trace_filename(trace_dir, fn_name)
                if sh.isfile(trace_fn):
                    LOG.debug("Removing %r trace file %r" % (app_name, trace_fn))
                    sh.unlink(trace_fn)
            else:
                msg = "Could not stop %r after %s attempts" % (app_name, attempts)
                raise excp.StopException(msg)

    def _extract_pid(self, filename):
        if sh.isfile(filename):
            try:
                return int(sh.load_file(filename).strip())
            except ValueError:
                return None
        else:
            return None

    def status(self, app_name):
        trace_dir = self.runtime.get_option('trace_dir')
        if not sh.isdir(trace_dir):
            return (STATUS_UNKNOWN, '')
        (pid_file, stderr_fn, stdout_fn) = self._form_file_names(FORK_TEMPL % (app_name))
        pid = self._extract_pid(pid_file)
        stderr = ''
        try:
            stderr = sh.load_file(stderr_fn)
        except IOError:
            pass
        stdout = ''
        try:
            stdout = sh.load_file(stdout_fn)
        except IOError:
            pass
        if pid and sh.is_running(pid):
            return (STATUS_STARTED, (stdout + stderr).strip())
        else:
            return (STATUS_UNKNOWN, (stdout + stderr).strip())

    def _form_file_names(self, file_name):
        trace_dir = self.runtime.get_option('trace_dir')
        return (sh.joinpths(trace_dir, file_name + ".pid"),
                sh.joinpths(trace_dir, file_name + ".stderr"),
                sh.joinpths(trace_dir, file_name + ".stdout"))

    def _do_trace(self, fn, kvs):
        trace_dir = self.runtime.get_option('trace_dir')
        run_trace = tr.TraceWriter(tr.trace_filename(trace_dir, fn))
        for (k, v) in kvs.items():
            run_trace.trace(k, v)
        return run_trace.filename()

    def _begin_start(self, app_name, app_pth, app_wkdir, args):
        fn_name = FORK_TEMPL % (app_name)
        (pid_fn, stderr_fn, stdout_fn) = self._form_file_names(fn_name)
        trace_info = dict()
        trace_info[PID_FN] = pid_fn
        trace_info[STDERR_FN] = stderr_fn
        trace_info[STDOUT_FN] = stdout_fn
        trace_info[ARGS] = json.dumps(args)
        trace_fn = self._do_trace(fn_name, trace_info)
        LOG.debug("Forking %r by running command %r with args (%s)" % (app_name, app_pth, " ".join(args)))
        with sh.Rooted(True):
            sh.fork(app_pth, app_wkdir, pid_fn, stdout_fn, stderr_fn, *args)
        return trace_fn

    def start(self, app_name, app_pth, app_dir, opts):
        return self._begin_start(app_name, app_pth, app_dir, opts)
