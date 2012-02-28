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

from runnerbase import RunnerBase
from devstack import exceptions as excp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import trace as tr

LOG = logging.getLogger("devstack.runners.fork")

#maximum for the number of available file descriptors (when not found)
MAXFD = 2048

#how many times we try to kill and how much sleep (seconds) between each try
MAX_KILL_TRY = 5
SLEEP_TIME = 1

#my type
RUN_TYPE = settings.RUN_TYPE_FORK
TYPE = settings.RUN_TYPE_TYPE

#trace constants
PID_FN = "PID_FN"
STDOUT_FN = "STDOUT_FN"
STDERR_FN = "STDERR_FN"
ARGS = "ARGS"
NAME = "NAME"
FORK_TEMPL = "%s.fork"

#run fork cmds as root?
ROOT_GO = True


class ForkRunner(RunnerBase):
    def __init__(self, cfg):
        RunnerBase.__init__(self, cfg)

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

    def stop(self, component_name, name, trace_dir):
        with sh.Rooted(ROOT_GO):
            if not trace_dir or not sh.isdir(trace_dir):
                msg = "No trace directory found from which to stop %s" % (name)
                raise excp.StopException(msg)
            fn_name = FORK_TEMPL % (name)
            (pid_file, stderr_fn, stdout_fn) = self._form_file_names(trace_dir, fn_name)
            trace_fn = tr.trace_fn(trace_dir, fn_name)
            if sh.isfile(pid_file) and sh.isfile(trace_fn):
                pid = int(sh.load_file(pid_file).strip())
                (killed, attempts) = self._stop_pid(pid)
                #trash the files
                if killed:
                    LOG.debug("Killed pid %s after %s attempts" % (pid, attempts))
                    LOG.debug("Removing pid file %s" % (pid_file))
                    sh.unlink(pid_file)
                    LOG.debug("Removing stderr file %s" % (stderr_fn))
                    sh.unlink(stderr_fn)
                    LOG.debug("Removing stdout file %s" % (stdout_fn))
                    sh.unlink(stdout_fn)
                    LOG.debug("Removing %s trace file %s" % (name, trace_fn))
                    sh.unlink(trace_fn)
                else:
                    msg = "Could not stop %s after %s attempts" % (name, attempts)
                    raise excp.StopException(msg)
            else:
                msg = "No pid or trace file could be found to stop %s in directory %s" % (name, trace_dir)
                raise excp.StopException(msg)

    def _form_file_names(self, tracedir, file_name):
        pidfile = sh.joinpths(tracedir, file_name + ".pid")
        stderr = sh.joinpths(tracedir, file_name + ".stderr")
        stdout = sh.joinpths(tracedir, file_name + ".stdout")
        return (pidfile, stderr, stdout)

    def _fork_start(self, program, appdir, pid_fn, stdout_fn, stderr_fn, *args):
        #first child, not the real program
        pid = os.fork()
        if pid == 0:
            #upon return the calling process shall be the session
            #leader of this new session,
            #shall be the process group leader of a new process group,
            #and shall have no controlling terminal.
            os.setsid()
            pid = os.fork()
            #fork to get daemon out - this time under init control
            #and now fully detached (no shell possible)
            if pid == 0:
                #move to where application should be
                if appdir:
                    os.chdir(appdir)
                #close other fds
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
                #now adjust stderr and stdout
                if stdout_fn:
                    stdoh = open(stdout_fn, "w")
                    os.dup2(stdoh.fileno(), sys.stdout.fileno())
                if stderr_fn:
                    stdeh = open(stderr_fn, "w")
                    os.dup2(stdeh.fileno(), sys.stderr.fileno())
                #now exec...
                #the arguments to the child process should
                #start with the name of the command being run
                prog_little = os.path.basename(program)
                actualargs = [prog_little] + list(args)
                os.execlp(program, *actualargs)
            else:
                #write out the child pid
                contents = str(pid) + os.linesep
                sh.write_file(pid_fn, contents, quiet=True)
                #not exit or sys.exit, this is recommended
                #since it will do the right cleanups that we want
                #not calling any atexit functions, which would
                #be bad right now
                os._exit(0)

    def _do_trace(self, fn, tracedir, kvs):
        tracefn = tr.touch_trace(tracedir, fn)
        runtrace = tr.Trace(tracefn)
        runtrace.trace(TYPE, RUN_TYPE)
        for (k, v) in kvs.items():
            runtrace.trace(k, v)
        return tracefn

    def start(self, component_name, name, runtime_info, tracedir):
        (program, appdir, program_args) = runtime_info
        fn_name = FORK_TEMPL % (name)
        (pidfile, stderrfn, stdoutfn) = self._form_file_names(tracedir, fn_name)
        trace_info = dict()
        trace_info[PID_FN] = pidfile
        trace_info[STDERR_FN] = stderrfn
        trace_info[STDOUT_FN] = stdoutfn
        trace_info[ARGS] = json.dumps(program_args)
        tracefn = self._do_trace(fn_name, tracedir, trace_info)
        LOG.debug("Forking [%s] by running command [%s]" % (name, program))
        with sh.Rooted(ROOT_GO):
            self._fork_start(program, appdir, pidfile, stdoutfn, stderrfn, *program_args)
        return tracefn
