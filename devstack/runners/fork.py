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
import os
import resource
import signal
import sys
import time

from devstack import exceptions as excp
from devstack import log as logging
from devstack import runner as base
from devstack import shell as sh
from devstack import trace as tr

LOG = logging.getLogger("devstack.runners.fork")

# Maximum for the number of available file descriptors (when not found)
MAXFD = 2048

# How many times we try to kill and how much sleep (seconds) between each try
MAX_KILL_TRY = 5
SLEEP_TIME = 1

# Trace constants
PID_FN = "PID_FN"
STDOUT_FN = "STDOUT_FN"
STDERR_FN = "STDERR_FN"
ARGS = "ARGS"
NAME = "NAME"
FORK_TEMPL = "%s.fork"


class ForkRunner(base.RunnerBase):
    def __init__(self, cfg, component_name, trace_dir):
        base.RunnerBase.__init__(self, cfg, component_name, trace_dir)

    def _stop_pid(self, pid):
        killed = False
        attempts = 0
        for _ in range(0, MAX_KILL_TRY):
            try:
                LOG.debug("Attempting to kill pid %s" % (pid))
                attempts += 1
                os.kill(pid, signal.SIGKILL)
                LOG.debug("Sleeping for %s seconds before next attempt to "\
                             "kill pid %s" % (SLEEP_TIME, pid))
                time.sleep(SLEEP_TIME)
            except OSError, e:
                ec = e.errno
                if ec == errno.ESRCH:
                    killed = True
                    break
                else:
                    LOG.debug("Sleeping for %s seconds before next attempt to kill pid %s" % (SLEEP_TIME, pid))
                    time.sleep(SLEEP_TIME)
        return (killed, attempts)

    def stop(self, app_name):
        with sh.Rooted(True):
            if not sh.isdir(self.trace_dir):
                msg = "No trace directory found from which to stop %r" % (app_name)
                raise excp.StopException(msg)
            fn_name = FORK_TEMPL % (app_name)
            (pid_file, stderr_fn, stdout_fn) = self._form_file_names(fn_name)
            trace_fn = tr.trace_fn(self.trace_dir, fn_name)
            if sh.isfile(pid_file) and sh.isfile(trace_fn):
                pid = int(sh.load_file(pid_file).strip())
                (killed, attempts) = self._stop_pid(pid)
                # Trash the files if it worked
                if killed:
                    LOG.debug("Killed pid %s after %s attempts" % (pid, attempts))
                    LOG.debug("Removing pid file %s" % (pid_file))
                    sh.unlink(pid_file)
                    LOG.debug("Removing stderr file %r" % (stderr_fn))
                    sh.unlink(stderr_fn)
                    LOG.debug("Removing stdout file %r" % (stdout_fn))
                    sh.unlink(stdout_fn)
                    LOG.debug("Removing %r trace file %r" % (app_name, trace_fn))
                    sh.unlink(trace_fn)
                else:
                    msg = "Could not stop %r after %s attempts" % (app_name, attempts)
                    raise excp.StopException(msg)
            else:
                msg = "No pid or trace file could be found to stop %r in directory %r" % (app_name, self.trace_dir)
                raise excp.StopException(msg)

    def _form_file_names(self, file_name):
        return (sh.joinpths(self.trace_dir, file_name + ".pid"),
                sh.joinpths(self.trace_dir, file_name + ".stderr"),
                sh.joinpths(self.trace_dir, file_name + ".stdout"))

    def _fork_start(self, program, app_dir, pid_fn, stdout_fn, stderr_fn, *args):
        # First child, not the real program
        pid = os.fork()
        if pid == 0:
            # Upon return the calling process shall be the session
            # leader of this new session,
            # shall be the process group leader of a new process group,
            # and shall have no controlling terminal.
            os.setsid()
            pid = os.fork()
            # Fork to get daemon out - this time under init control
            # and now fully detached (no shell possible)
            if pid == 0:
                # Move to where application should be
                if app_dir:
                    os.chdir(app_dir)
                # Close other fds (or try)
                limits = resource.getrlimit(resource.RLIMIT_NOFILE)
                mkfd = limits[1]
                if mkfd == resource.RLIM_INFINITY:
                    mkfd = MAXFD
                for fd in range(0, mkfd):
                    try:
                        os.close(fd)
                    except OSError:
                        #not open, thats ok
                        pass
                # Now adjust stderr and stdout
                if stdout_fn:
                    stdoh = open(stdout_fn, "w")
                    os.dup2(stdoh.fileno(), sys.stdout.fileno())
                if stderr_fn:
                    stdeh = open(stderr_fn, "w")
                    os.dup2(stdeh.fileno(), sys.stderr.fileno())
                # Now exec...
                # Note: The arguments to the child process should
                # start with the name of the command being run
                prog_little = os.path.basename(program)
                actualargs = [prog_little] + list(args)
                os.execlp(program, *actualargs)
            else:
                # Write out the child pid
                contents = str(pid) + os.linesep
                sh.write_file(pid_fn, contents, quiet=True)
                # Not exit or sys.exit, this is recommended
                # since it will do the right cleanups that we want
                # not calling any atexit functions, which would
                # be bad right now
                os._exit(0)

    def _do_trace(self, fn, kvs):
        run_trace = tr.TraceWriter(tr.trace_fn(self.trace_dir, fn))
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
            self._fork_start(app_pth, app_wkdir, pid_fn, stdout_fn, stderr_fn, *args)
        return trace_fn

    def start(self, app_name, app_pth, app_dir, opts):
        return self._begin_start(app_name, app_pth, app_dir, opts)
