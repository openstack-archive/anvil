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

import errno
import json
import os
import resource
import signal
import sys
import time

from devstack import exceptions as excp
from devstack import log as logging
from devstack import shell as sh
from devstack import trace as tr

# Maximum for the number of available file descriptors (when not found)
MAXFD = 2048
MAX_KILL_TRY = 5
SLEEP_TIME = 1

LOG = logging.getLogger("devstack.runners.fork")

#trace constants
TYPE = "TYPE"
RUN_TYPE = "FORK"
PID_FN = "PID_FN"
STDOUT_FN = "STDOUT_FN"
STDERR_FN = "STDERR_FN"
ARGS = "ARGS"
NAME = "NAME"
FORK_TEMPL = "%s.fork"


class ForkRunner(object):
    def __init__(self):
        pass

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
                    LOG.info("Sleeping for %s seconds before next attempt to kill pid %s" % (SLEEP_TIME, pid))
                    time.sleep(SLEEP_TIME)
        return (killed, attempts)

    def stop(self, name, *args, **kargs):
        trace_dir = kargs.get("trace_dir")
        if(not trace_dir or not sh.isdir(trace_dir)):
            msg = "No trace directory found from which to stop %s" % (name)
            raise excp.StopException(msg)
        fn_name = FORK_TEMPL % (name)
        (pid_file, stderr_fn, stdout_fn) = self._form_file_names(trace_dir, fn_name)
        trace_fn = tr.trace_fn(trace_dir, fn_name)
        if(sh.isfile(pid_file) and sh.isfile(trace_fn)):
            pid = int(sh.load_file(pid_file).strip())
            (killed, attempts) = self._stop_pid(pid)
            #trash the files
            if(killed):
                LOG.info("Killed pid %s after %s attempts" % (pid, attempts))
                LOG.info("Removing pid file %s" % (pid_file))
                sh.unlink(pid_file)
                LOG.info("Removing stderr file %s" % (stderr_fn))
                sh.unlink(stderr_fn)
                LOG.info("Removing stdout file %s" % (stdout_fn))
                sh.unlink(stdout_fn)
                LOG.info("Removing %s trace file %s" % (name, trace_fn))
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
        if(pid == 0):
            #upon return the calling process shall be the session
            #leader of this new session,
            #shall be the process group leader of a new process group,
            #and shall have no controlling terminal.
            os.setsid()
            pid = os.fork()
            #fork to get daemon out - this time under init control
            #and now fully detached (no shell possible)
            if(pid == 0):
                #move to where application should be
                if(appdir):
                    os.chdir(appdir)
                #close other fds
                limits = resource.getrlimit(resource.RLIMIT_NOFILE)
                mkfd = limits[1]
                if(mkfd == resource.RLIM_INFINITY):
                    mkfd = MAXFD
                for fd in range(0, mkfd):
                    try:
                        os.close(fd)
                    except OSError:
                        #not open, thats ok
                        pass
                #now adjust stderr and stdout
                if(stdout_fn):
                    stdoh = open(stdout_fn, "w")
                    os.dup2(stdoh.fileno(), sys.stdout.fileno())
                if(stderr_fn):
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

    def start(self, name, program, *args, **kargs):
        tracedir = kargs.get("trace_dir")
        appdir = kargs.get("app_dir")
        fn_name = FORK_TEMPL % (name)
        (pidfile, stderrfn, stdoutfn) = self._form_file_names(tracedir, fn_name)
        tracefn = tr.touch_trace(tracedir, fn_name)
        runtrace = tr.Trace(tracefn)
        runtrace.trace(TYPE, RUN_TYPE)
        runtrace.trace(PID_FN, pidfile)
        runtrace.trace(STDERR_FN, stderrfn)
        runtrace.trace(STDOUT_FN, stdoutfn)
        runtrace.trace(ARGS, json.dumps(args))
        LOG.info("Forking [%s] by running command [%s]" % (name, program))
        self._fork_start(program, appdir, pidfile, stdoutfn, stderrfn, *args)
        return tracefn
