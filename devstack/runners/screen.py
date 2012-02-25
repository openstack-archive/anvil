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
import re
import time

from devstack import exceptions as excp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import trace as tr
from devstack import utils

LOG = logging.getLogger("devstack.runners.screen")

#my type
RUN_TYPE = settings.RUN_TYPE_SCREEN
TYPE = settings.RUN_TYPE_TYPE

#trace constants
SCREEN_TEMPL = "%s.screen"
ARGS = "ARGS"
NAME = "NAME"
SESSION_ID = 'SESSION_ID'

#screen session name
SESSION_NAME = 'stack'
SESSION_NAME_MTCHER = re.compile(r"^\s*([\d]+\.%s)\s*(.*)$" % (SESSION_NAME), re.I)

#how we setup screens status bar
STATUS_BAR_CMD = r'hardstatus alwayslastline "%-Lw%{= BW}%50>%n%f* %t%{-}%+Lw%< %= %H"'

#cmds
SESSION_INIT = ['screen', '-d', '-m', '-S', SESSION_NAME, '-t', SESSION_NAME, '-s', "/bin/bash"]
BAR_INIT = ['screen', '-r', SESSION_NAME, '-X', STATUS_BAR_CMD]
CMD_INIT = ['screen', '-S', '%SESSION_NAME%', '-X', 'screen', '-t', "%NAME%"]
CMD_KILL = ['screen', '-S', '%SESSION_NAME%', '-p', "%NAME%", '-X', 'kill']
CMD_WIPE = ['screen', '-S', '%SESSION_NAME%', '-wipe']
CMD_START = ['screen', '-S', '%SESSION_NAME%', '-p', "%NAME%", '-X', 'stuff', "\"%CMD%\r\""]
LIST_CMD = ['screen', '-ls']
SCREEN_KILLER = ['screen', '-X', '-S', '%SCREEN_ID%', 'quit']

#where our screen sockets will go
SCREEN_SOCKET_DIR = "/tmp/devstack-sockets"
SCREEN_SOCKET_PERM = 0700

#used to wait until started before we can run the actual start cmd
WAIT_ONLINE_TO = settings.WAIT_ALIVE_SECS

#run screen as root?
ROOT_GO = True


class ScreenRunner(object):
    def __init__(self, cfg):
        self.cfg = cfg

    def stop(self, name, *args, **kargs):
        tracedir = kargs["trace_dir"]
        fn_name = SCREEN_TEMPL % (name)
        trace_fn = tr.trace_fn(tracedir, fn_name)
        session_id = self._find_session(name, trace_fn)
        self._do_stop(name, session_id)
        sh.unlink(trace_fn)

    def _find_session(self, name, trace_fn):
        session_id = None
        for (key, value) in tr.parse_fn(trace_fn):
            if key == SESSION_ID and value:
                session_id = value
        if not session_id:
            msg = "Could not find a screen session id for %s" % (name)
            raise excp.StopException(msg)
        return session_id

    def _do_stop(self, name, session_id):
        mp = dict()
        mp['SESSION_NAME'] = session_id
        mp['NAME'] = name
        LOG.info("Stopping program running in session %s in window named %s." % (session_id, name))
        kill_cmd = self._gen_cmd(CMD_KILL, mp)
        sh.execute(*kill_cmd,
                shell=True,
                run_as_root=ROOT_GO,
                env_overrides=self.get_env(),
                check_exit_code=False)
        #we have really no way of knowing if it worked or not
        #screen sux...
        wipe_cmd = self._gen_cmd(CMD_WIPE, mp)
        sh.execute(*wipe_cmd,
                shell=True,
                run_as_root=ROOT_GO,
                env_overrides=self.get_env(),
                check_exit_code=False)

    def get_env(self):
        env = dict()
        env['SCREENDIR'] = SCREEN_SOCKET_DIR
        return env

    def _gen_cmd(self, base_cmd, params=dict()):
        full_cmd = base_cmd
        actual_cmd = list()
        for piece in full_cmd:
            actual_cmd.append(utils.param_replace(piece, params))
        return actual_cmd

    def _active_sessions(self):
        knowns = list()
        list_cmd = self._gen_cmd(LIST_CMD)
        (sysout, _) = sh.execute(*list_cmd,
                            check_exit_code=False,
                            run_as_root=ROOT_GO,
                            env_overrides=self.get_env())
        if sysout.lower().find("No Sockets found") != -1:
            return knowns
        for line in sysout.splitlines():
            mtch = SESSION_NAME_MTCHER.match(line)
            if mtch:
                knowns.append(mtch.group(1))
        return knowns

    def _get_session(self):
        sessions = self._active_sessions()
        LOG.debug("Found sessions [%s]" % ", ".join(sessions))
        if not sessions:
            return None
        if len(sessions) > 1:
            msg = [
                    "You are running multiple screen sessions [%s], please reduce the set to zero or one." % (", ".join(sessions)),
                  ]
            for s in sorted(sessions):
                mp = {'SCREEN_ID': s}
                cmd_msg = self._gen_cmd(SCREEN_KILLER, mp)
                env = self.get_env()
                for (k, v) in env.items():
                    cmd_msg.insert(0, "%s=%s" % (k, v))
                msg.append("Try running '%s' to quit that session." % (" ".join(cmd_msg)))
            raise excp.StartException(utils.joinlinesep(msg))
        return sessions[0]

    def _do_screen_init(self):
        LOG.info("Creating a new screen session named %s." % (SESSION_NAME))
        session_init_cmd = self._gen_cmd(SESSION_INIT)
        sh.execute(*session_init_cmd,
                shell=True,
                run_as_root=ROOT_GO,
                env_overrides=self.get_env())
        LOG.info("Waiting %s seconds before we attempt to set the title bar for that session." % (WAIT_ONLINE_TO))
        time.sleep(WAIT_ONLINE_TO)
        bar_init_cmd = self._gen_cmd(BAR_INIT)
        sh.execute(*bar_init_cmd,
                shell=True,
                run_as_root=ROOT_GO,
                env_overrides=self.get_env())

    def _do_start(self, session, prog_name, cmd):
        init_cmd = list()
        mp = dict()
        run_cmd = " ".join(cmd)
        mp['SESSION_NAME'] = session
        mp['NAME'] = prog_name
        mp['CMD'] = run_cmd
        init_cmd = self._gen_cmd(CMD_INIT, mp)
        LOG.info("Creating a new screen window named %s in session %s." % (prog_name, session))
        sh.execute(*init_cmd,
            shell=True,
            run_as_root=ROOT_GO,
            env_overrides=self.get_env())
        LOG.info("Waiting %s seconds before we attempt to run command [%s] in that window." % (WAIT_ONLINE_TO, run_cmd))
        time.sleep(WAIT_ONLINE_TO)
        start_cmd = self._gen_cmd(CMD_START, mp)
        sh.execute(*start_cmd,
            shell=True,
            run_as_root=ROOT_GO,
            env_overrides=self.get_env())
        #we have really no way of knowing if it worked or not
        #screen sux...

    def _do_socketdir_init(self):
        socketdir = SCREEN_SOCKET_DIR
        with sh.Rooted(ROOT_GO):
            if not sh.isdir(socketdir):
                dirs = sh.mkdirslist(socketdir)
                for d in dirs:
                    sh.chmod(d, SCREEN_SOCKET_PERM)
        return socketdir

    def _begin_start(self, name, program, args, tracedir):
        fn_name = SCREEN_TEMPL % (name)
        tracefn = tr.touch_trace(tracedir, fn_name)
        runtrace = tr.Trace(tracefn)
        runtrace.trace(TYPE, RUN_TYPE)
        runtrace.trace(NAME, name)
        runtrace.trace(ARGS, json.dumps(args))
        full_cmd = [program] + list(args)
        session_name = self._get_session()
        if session_name is None:
            self._do_screen_init()
            session_name = self._get_session()
            if session_name is None:
                msg = "After initializing screen with session named %s, no screen session with that name was found!" % (SESSION_NAME)
                raise excp.StartException(msg)
        runtrace.trace(SESSION_ID, session_name)
        self._do_start(session_name, name, full_cmd)
        return tracefn

    def start(self, name, program, *program_args, **kargs):
        self._do_socketdir_init()
        tracedir = kargs["trace_dir"]
        args = list(program_args)
        return self._begin_start(name, program, args, tracedir)
