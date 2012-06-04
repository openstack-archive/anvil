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
import tempfile
import weakref

from anvil import date
from anvil import exceptions as excp
from anvil import log as logging
from anvil import settings
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils

from anvil.runners import base

LOG = logging.getLogger(__name__)

# Trace constants
SCREEN_TEMPL = "%s.screen"
ARGS = "ARGS"
NAME = "NAME"
SESSION_ID = 'SESSION_ID'

# Screen session name
SESSION_NAME = 'stack'
SESSION_DEF_TITLE = SESSION_NAME
SESSION_NAME_MTCHER = re.compile(r"^\s*([\d]+\.%s)\s*(.*)$" % (SESSION_NAME))

# How we setup screens status bar
STATUS_BAR_CMD = r'hardstatus alwayslastline "%-Lw%{= BW}%50>%n%f* %t%{-}%+Lw%< %= %H"'

# Screen commands/template commands
SESSION_INIT = ['screen', '-d', '-m', '-S', SESSION_NAME, '-t', SESSION_DEF_TITLE, '-s', "/bin/bash"]
BAR_INIT = ['screen', '-r', SESSION_NAME, '-X', STATUS_BAR_CMD]
CMD_INIT = ['screen', '-S', '%SESSION_NAME%', '-X', 'screen', '-t', "%NAME%"]
CMD_KILL = ['screen', '-S', '%SESSION_NAME%', '-p', "%NAME%", '-X', 'kill']
CMD_WIPE = ['screen', '-S', '%SESSION_NAME%', '-wipe']
CMD_START = ['screen', '-S', '%SESSION_NAME%', '-p', "%NAME%", '-X', 'stuff', "\"%CMD%\r\""]
LIST_CMD = ['screen', '-ls']
SCREEN_KILLER = ['screen', '-X', '-S', '%SCREEN_ID%', 'quit']

# Where our screen sockets will go
SCREEN_SOCKET_DIR_NAME = "forged-screen-sockets"
SCREEN_SOCKET_PERM = 0700

# Screen RC file
SCREEN_RC = settings.RC_FN_TEMPL % ('screen')


class ScreenRunner(base.Runner):
    def __init__(self, runtime):
        base.Runner.__init__(self, runtime)
        self.cfg = self.runtime.cfg
        self.socket_dir = sh.joinpths(tempfile.gettempdir(), SCREEN_SOCKET_DIR_NAME)
        self.wait_time = max(self.cfg.getint('DEFAULT', 'service_wait_seconds'), 1)

    def stop(self, app_name):
        trace_fn = tr.trace_fn(self.runtime.get_option('trace_dir'), SCREEN_TEMPL % (app_name))
        session_id = self._find_session(app_name, trace_fn)
        self._do_stop(app_name, session_id)
        sh.unlink(trace_fn)

    def _find_session(self, app_name, trace_fn):
        session_id = None
        for (key, value) in tr.TraceReader(trace_fn).read():
            if key == SESSION_ID and value:
                session_id = value
        if not session_id:
            msg = "Could not find a screen session id for %r in file %r" % (app_name, trace_fn)
            raise excp.StopException(msg)
        return session_id

    def _do_stop(self, app_name, session_id):
        mp = dict()
        mp['SESSION_NAME'] = session_id
        mp['NAME'] = app_name
        LOG.debug("Stopping program running in session %r in window named %r" % (session_id, app_name))
        kill_cmd = self._gen_cmd(CMD_KILL, mp)
        sh.execute(*kill_cmd,
                shell=True,
                run_as_root=True,
                env_overrides=self._get_env(),
                check_exit_code=False)
        # We have really no way of knowing if it worked or not, screen sux...
        wipe_cmd = self._gen_cmd(CMD_WIPE, mp)
        sh.execute(*wipe_cmd,
                shell=True,
                run_as_root=True,
                env_overrides=self._get_env(),
                check_exit_code=False)

    def _get_env(self):
        env = dict()
        env['SCREENDIR'] = self.socket_dir
        return env

    def _gen_cmd(self, base_cmd, params=dict()):
        return utils.param_replace_list(base_cmd, params, ignore_missing=True)

    def _active_sessions(self):
        knowns = list()
        list_cmd = self._gen_cmd(LIST_CMD)
        (sysout, _) = sh.execute(*list_cmd,
                            check_exit_code=False,
                            run_as_root=True,
                            env_overrides=self._get_env())
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
                env = self._get_env()
                for (k, v) in env.items():
                    cmd_msg.insert(0, "%s=%s" % (k, v))
                msg.append("Try running %r to quit that session." % (" ".join(cmd_msg)))
            raise excp.StartException(utils.joinlinesep(msg))
        return sessions[0]

    def _do_screen_init(self):
        LOG.debug("Creating a new screen session named %r" % (SESSION_NAME))
        session_init_cmd = self._gen_cmd(SESSION_INIT)
        sh.execute(*session_init_cmd,
                shell=True,
                run_as_root=True,
                env_overrides=self._get_env())
        LOG.debug("Waiting %s seconds before we attempt to set the title bar for that session." % (self.wait_time))
        sh.sleep(self.wait_time)
        bar_init_cmd = self._gen_cmd(BAR_INIT)
        sh.execute(*bar_init_cmd,
                shell=True,
                run_as_root=True,
                env_overrides=self._get_env())

    def _do_start(self, session, prog_name, cmd):
        init_cmd = list()
        mp = dict()
        run_cmd = " ".join(cmd)
        mp['SESSION_NAME'] = session
        mp['NAME'] = prog_name
        mp['CMD'] = run_cmd
        init_cmd = self._gen_cmd(CMD_INIT, mp)
        LOG.debug("Creating a new screen window named %r in session %r" % (prog_name, session))
        sh.execute(*init_cmd,
            shell=True,
            run_as_root=True,
            env_overrides=self._get_env())
        LOG.debug("Waiting %s seconds before we attempt to run command %r in that window." % (self.wait_time, run_cmd))
        sh.sleep(self.wait_time)
        start_cmd = self._gen_cmd(CMD_START, mp)
        sh.execute(*start_cmd,
            shell=True,
            run_as_root=True,
            env_overrides=self._get_env())
        # We have really no way of knowing if it worked or not, screen sux...

    def _do_socketdir_init(self, socketdir, perm):
        LOG.debug("Making screen socket directory %r (with permissions %o)" % (socketdir, perm))
        with sh.Rooted(True):
            dirs = sh.mkdirslist(socketdir)
            for d in dirs:
                sh.chmod(d, perm)

    def _begin_start(self, name, program, args):
        run_trace = tr.TraceWriter(tr.trace_fn(self.runtime.get_option('trace_dir'), SCREEN_TEMPL % (name)))
        run_trace.trace(NAME, name)
        run_trace.trace(ARGS, json.dumps(args))
        full_cmd = [program] + list(args)
        session_name = self._get_session()
        inited_screen = False
        if session_name is None:
            inited_screen = True
            self._do_screen_init()
            session_name = self._get_session()
            if session_name is None:
                msg = "After initializing screen with session named %r, no screen session with that name was found!" % (SESSION_NAME)
                raise excp.StartException(msg)
        run_trace.trace(SESSION_ID, session_name)
        if inited_screen or not sh.isfile(SCREEN_RC):
            rc_gen = ScreenRcGenerator(self)
            rc_contents = rc_gen.create(session_name, self._get_env())
            out_fn = sh.abspth(SCREEN_RC)
            LOG.info("Writing your created screen rc file to %r" % (out_fn))
            sh.write_file(out_fn, rc_contents)
        self._do_start(session_name, name, full_cmd)
        return run_trace.filename()

    def start(self, app_name, app_pth, app_dir, opts):
        if not sh.isdir(self.socket_dir):
            self._do_socketdir_init(self.socket_dir, SCREEN_SOCKET_PERM)
        return self._begin_start(app_name, app_pth, opts)


class ScreenRcGenerator(object):
    def __init__(self, runner):
        self.runner = weakref.proxy(runner)

    def _generate_help(self, session_name, env_exports):
        lines = list()
        lines.append("# Screen help stuff")
        cmd_pieces = list()
        for (k, v) in env_exports.items():
            cmd_pieces.append("%s=%s" % (k, sh.shellquote(v)))
        cmd_pieces.append("screen -r %s" % (session_name))
        cmd_pieces.insert(0, "sudo")
        lines.append("# To connect to this session run the following command: ")
        lines.append("# %s" % (" ".join(cmd_pieces)))
        lines.append("")
        return lines

    def _generate_lines(self, session_name, env_exports):
        lines = list()
        lines.append("# RC file generated on %s" % (date.rcf8222date()))
        lines.append("")
        if env_exports:
            lines.append("# Environment settings (these will need to be exported)")
            for (k, v) in env_exports.items():
                lines.append("# export %s=%s" % (k, sh.shellquote(v)))
            lines.append("")
        lines.append("# Screen sockets & programs were created/ran as the root user")
        lines.append("# So you will need to run as user root (or sudo) to enter the following sessions")
        lines.append("")
        lines.append("# Session settings")
        lines.append("sessionname %s" % (session_name))
        lines.append(STATUS_BAR_CMD)
        lines.append("screen -t %s bash" % (SESSION_DEF_TITLE))
        lines.append("")
        lines.extend(self._generate_help(session_name, env_exports))
        return lines

    def create(self, session_name, env_exports):
        lines = self._generate_lines(session_name, env_exports)
        contents = utils.joinlinesep(*lines)
        return contents
