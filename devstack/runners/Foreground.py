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

import Runner
import Util
import Exceptions
from Exceptions import (StartException, StopException)
import Logger
import Shell
from Shell import (unlink, mkdir, joinpths, write_file,
                   load_file, isfile)
import Trace

# Maximum for the number of available file descriptors (when not found)
MAXFD = 2048
MAX_KILL_TRY = 4
SLEEP_TIME = 1

LOG = Logger.getLogger("install.runners.foreground")

#trace constants
RUN = Runner.RUN_TYPE
RUN_TYPE = "FORK"
PID_FN = "PID_FN"
STDOUT_FN = "STDOUT_FN"
STDERR_FN = "STDERR_FN"
NAME = "NAME"


class ForegroundRunner(Runner.Runner):
    def __init__(self):
        Runner.Runner.__init__(self)

    def stop(self, name, *args, **kargs):
        rootdir = kargs.get("trace_dir")
        pidfile = joinpths(rootdir, name + ".pid")
        stderr = joinpths(rootdir, name + ".stderr")
        stdout = joinpths(rootdir, name + ".stdout")
        tfname = Trace.trace_fn(rootdir, name)
        if(isfile(pidfile) and isfile(tfname)):
            pid = int(load_file(pidfile).strip())
            killed = False
            lastmsg = ""
            attempts = 1
            for attempt in range(0, MAX_KILL_TRY):
                try:
                    os.kill(pid, signal.SIGKILL)
                    attempts += 1
                except OSError as (ec, msg):
                    if(ec == errno.ESRCH):
                        killed = True
                        break
                    else:
                        lastmsg = msg
                        time.sleep(SLEEP_TIME)
            #trash the files
            if(killed):
                LOG.info("Killed pid %s in %s attempts" % (str(pid), str(attempts)))
                LOG.info("Removing pid file %s" % (pidfile))
                unlink(pidfile)
                LOG.info("Removing stderr file %s" % (stderr))
                unlink(stderr)
                LOG.info("Removing stdout file %s" % (stdout))
                unlink(stdout)
                LOG.info("Removing %s trace file %s" % (name, tfname))
                unlink(tfname)
            else:
                msg = "Could not stop program named %s after %s attempts - [%s]" % (name, MAX_KILL_TRY, lastmsg)
                raise StopException(msg)
        else:
            msg = "No pid file could be found to terminate at %s" % (pidfile)
            raise StopException(msg)

    def start(self, name, program, *args, **kargs):
        tracedir = kargs.get("trace_dir")
        appdir = kargs.get("app_dir")
        pidfile = joinpths(tracedir, name + ".pid")
        stderr = joinpths(tracedir, name + ".stderr")
        stdout = joinpths(tracedir, name + ".stdout")
        tracefn = Trace.trace_fn(tracedir, name)
        tracefn = Trace.touch_trace(tracedir, name)
        runtrace = Trace.Trace(tracefn)
        runtrace.trace(RUN, RUN_TYPE)
        runtrace.trace(PID_FN, pidfile)
        runtrace.trace(STDERR_FN, stderr)
        runtrace.trace(STDOUT_FN, stdout)
        #fork to get daemon out
        pid = os.fork()
        if(pid == 0):
            os.setsid()
            pid = os.fork()
            #fork to get daemon out - this time under init control
            #and now fully detached (no shell possible)
            if(pid == 0):
                #move to where application should be
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
                stdoh = open(stdout, "w")
                stdeh = open(stderr, "w")
                os.dup2(stdoh.fileno(), sys.stdout.fileno())
                os.dup2(stdeh.fileno(), sys.stderr.fileno())
                #now exec...
                #the arguments to the child process should
                #start with the name of the command being run
                actualargs = [program] + list(args)
                os.execlp(program, *actualargs)
            else:
                #write out the child pid
                contents = str(pid) + "\n"
                write_file(pidfile, contents)
                #not exit or sys.exit, this is recommended
                #since it will do the right cleanups that we want
                #not calling any atexit functions, which would
                #be bad right now
                os._exit(0)
        else:
            return tracefn
