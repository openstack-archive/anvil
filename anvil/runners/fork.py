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

import errno
import json

from anvil import exceptions as excp
from anvil import log as logging
from anvil import runners as base
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils

from anvil.components import (STATUS_STARTED, STATUS_UNKNOWN)

LOG = logging.getLogger(__name__)

PID_FN = "PID_FN"
STDOUT_FN = "STDOUT_FN"
STDERR_FN = "STDERR_FN"
ARGS = "ARGS"
NAME = "NAME"
FORK_TEMPL = "%s.fork"


class ForkFiles(object):

    def __init__(self, pid, stdout, stderr, trace=None):
        self.pid = pid
        self.stdout = stdout
        self.stderr = stderr
        self.trace = trace

    def extract_pid(self):
        # Load the pid file and take out the pid from it...
        #
        # Typically said file has a integer pid in it so load said file
        # and covert its contents to an int or fail trying...
        if self.pid:
            try:
                return int(sh.load_file(self.pid).strip())
            except (ValueError, TypeError):
                return None
        else:
            return None

    def as_list(self):
        possibles = [self.pid, self.stdout, self.stderr, self.trace]
        return [i for i in possibles if i is not None]

    def as_dict(self):
        return {
            PID_FN: self.pid,
            STDOUT_FN: self.stdout,
            STDERR_FN: self.stderr,
        }


class ForkRunner(base.Runner):

    def stop(self, app_name):
        # The location of the pid file should be in the attached
        # runtimes trace directory, so see if we can find said file
        # and then attempt to kill the pid that exists in that file
        # which if succesffully will signal to the rest of this code
        # that we can go through and cleanup the other remnants of said
        # pid such as the stderr/stdout files that were being written to...
        trace_dir = self.runtime.get_option('trace_dir')
        if not sh.isdir(trace_dir):
            msg = "No trace directory found from which to stop: %r" % (
                app_name)
            raise excp.StopException(msg)
        with sh.Rooted(True):
            fork_fns = self._form_file_names(app_name)
            skip_kill = True
            pid = None
            try:
                pid = fork_fns.extract_pid()
                skip_kill = False
            except IOError as e:
                if e.errno == errno.ENOENT:
                    pass
                else:
                    skip_kill = False
            if not skip_kill and pid is None:
                msg = "Could not extract a valid pid from %r" % (fork_fns.pid)
                raise excp.StopException(msg)
            # Bother trying to kill said process?
            if not skip_kill:
                (killed, attempts) = sh.kill(pid)
            else:
                (killed, attempts) = (True, 0)
            # Trash the files if it worked
            if killed:
                if not skip_kill:
                    LOG.debug(
                        "Killed pid '%s' after %s attempts.",
                        pid,
                        attempts)
                for leftover_fn in fork_fns.as_list():
                    if sh.exists(leftover_fn):
                        LOG.debug(
                            "Removing forking related file %r",
                            (leftover_fn))
                        sh.unlink(leftover_fn)
            else:
                msg = "Could not stop %r after %s attempts" % (
                    app_name, attempts)
                raise excp.StopException(msg)

    def status(self, app_name):
        # Attempt to find the status of a given app by finding where that apps
        # pid file is and loading said pids details (from stderr/stdout) files
        # that should exist as well as by using shell utilities to determine
        # if said pid is still running...
        trace_dir = self.runtime.get_option('trace_dir')
        if not sh.isdir(trace_dir):
            return (STATUS_UNKNOWN, '')
        fork_fns = self._form_file_names(app_name)
        pid = fork_fns.extract_pid()
        stderr = ''
        try:
            stderr = sh.load_file(fork_fns.stderr)
        except (IOError, ValueError, TypeError):
            pass
        stdout = ''
        try:
            stdout = sh.load_file(fork_fns.stdout)
        except (IOError, ValueError, TypeError):
            pass
        details = {
            'STDOUT': stdout,
            'STDERR': stderr,
        }
        if pid is not None and sh.is_running(pid):
            return (STATUS_STARTED, details)
        else:
            return (STATUS_UNKNOWN, details)

    def _form_file_names(self, app_name):
        # Form all files names which should be connected to the given forked
        # application name
        fork_fn = FORK_TEMPL % (app_name)
        trace_dir = self.runtime.get_option('trace_dir')
        trace_fn = None
        if trace_dir:
            trace_fn = tr.trace_filename(trace_dir, fork_fn)
        base_fork_fn = sh.joinpths(trace_dir, fork_fn)
        return ForkFiles(pid=base_fork_fn + ".pid",
                         stdout=base_fork_fn + ".stdout",
                         stderr=base_fork_fn + ".stderr",
                         trace=trace_fn)

    def _begin_start(self, app_name, app_pth, app_wkdir, args):
        fork_fns = self._form_file_names(app_name)
        trace_fn = fork_fns.trace
        # Ensure all arguments for this app in string format
        args = [str(i) for i in args if i is not None]
        if trace_fn:
            # Not needed, but useful to know where the files are located at
            #
            # TODO(harlowja): use this info instead of forming the filenames
            # repeatly
            trace_info = {}
            trace_info.update(fork_fns.as_dict())
            # Useful to know what args were sent along
            trace_info[ARGS] = json.dumps(args)
            run_trace = tr.TraceWriter(trace_fn)
            for (k, v) in trace_info.items():
                if v is not None:
                    run_trace.trace(k, v)
        LOG.debug(
            "Forking %r by running command %r with args (%s)" %
            (app_name, app_pth, " ".join(args)))
        with sh.Rooted(True):
            sh.fork(
                app_pth,
                app_wkdir,
                fork_fns.pid,
                fork_fns.stdout,
                fork_fns.stderr,
                *
                args)
        return trace_fn

    def _post_start(self, app_name):
        fork_fns = self._form_file_names(app_name)
        utils.log_iterable(fork_fns.as_list(),
                           header="Forked %s with details in the following files" % (
                               app_name),
                           logger=LOG)

    def start(self, app_name, app_pth, app_dir, opts):
        trace_fn = self._begin_start(app_name, app_pth, app_dir, opts)
        self._post_start(app_name)
        return trace_fn
