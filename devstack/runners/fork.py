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

import os
import sys
import resource
import signal
import errno
import time

from devstack import exceptions as excp
from devstack import log as logging
from devstack import runner
from devstack import shell as sh
from devstack import trace as tr
from devstack import utils


# Maximum for the number of available file descriptors (when not found)
MAXFD = 2048
MAX_KILL_TRY = 5
SLEEP_TIME = 1

LOG = logging.getLogger("devstack.runners.foreground")

#trace constants
RUN = runner.RUN_TYPE
RUN_TYPE = "FORK"
PID_FN = "PID_FN"
STDOUT_FN = "STDOUT_FN"
STDERR_FN = "STDERR_FN"
NAME = "NAME"
FORK_TEMPL = "%s.fork"


class ForkRunner(runner.Runner):
    def __init__(self):
        runner.Runner.__init__(self)

    def _stop_pid(self, pid):
        killed = False
        lastmsg = ""
        for attempt in range(0, MAX_KILL_TRY):
            try:
                LOG.info("Attempting to kill pid %s" % (pid))
                os.kill(pid, signal.SIGKILL)
                LOG.info("Sleeping for %s seconds before next attempt to kill pid %s" % (SLEEP_TIME, pid))
                time.sleep(SLEEP_TIME)
            except OSError as (ec, msg):
                if(ec == errno.ESRCH):
                    killed = True
                    break
                else:
                    lastmsg = "[Errno: %s] %s" % (ec, msg)
                    LOG.info("Sleeping for %s seconds before next attempt to kill pid %s" % (SLEEP_TIME, pid))
                    time.sleep(SLEEP_TIME)
        return killed

    def stop(self, name, *args, **kargs):
        tracedir = kargs.get("trace_dir")
        fn_name = FORK_TEMPL % (name)
        (pidfile, stderr, stdout) = self._form_file_names(tracedir, fn_name)
        tfname = tr.trace_fn(tracedir, fn_name)
        if(isfile(pidfile) and isfile(tfname)):
            pid = int(load_file(pidfile).strip())
            killed = self._stop_pid(pid)
            #trash the files
            if(killed):
                LOG.info("Killed pid %s" % (pid))
                LOG.info("Removing pid file %s" % (pidfile))
                unlink(pidfile)
                LOG.info("Removing stderr file %s" % (stderr))
                unlink(stderr)
                LOG.info("Removing stdout file %s" % (stdout))
                unlink(stdout)
                LOG.info("Removing %s trace file %s" % (name, tfname))
                unlink(tfname)
            else:
                msg = "Could not stop program named %s after %s attempts" % (name, MAX_KILL_TRY)
                raise StopException(msg)
        else:
            msg = "No pid or trace file could be found to terminate at %s" % (tracedir)
            raise StopException(msg)

    def _form_file_names(self, tracedir, file_name):
        pidfile = joinpths(tracedir, file_name + ".pid")
        stderr = joinpths(tracedir, file_name + ".stderr")
        stdout = joinpths(tracedir, file_name + ".stdout")
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
                actualargs = [program] + list(args)
                os.execlp(program, *actualargs)
            else:
                #write out the child pid
                contents = str(pid) + os.linesep
                write_file(pid_fn, contents)
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
        runtrace.trace(RUN, RUN_TYPE)
        runtrace.trace(PID_FN, pidfile)
        runtrace.trace(STDERR_FN, stderrfn)
        runtrace.trace(STDOUT_FN, stdoutfn)
        LOG.info("Forking [%s] by running command [%s]" % (name, program))
        self._fork_start(program, appdir, pidfile, stdoutfn, stderrfn, *args)
        return tracefn
