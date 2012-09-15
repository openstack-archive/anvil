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
import getpass
import grp
import os
import pwd
import resource
import shutil
import signal
import socket
import subprocess
import sys
import time

from anvil import env
from anvil import exceptions as excp
from anvil import log as logging
from anvil import type_utils as tu

LOG = logging.getLogger(__name__)

SHELL_QUOTE_REPLACERS = {
    "\"": "\\\"",
    "(": "\\(",
    ")": "\\)",
    "$": '\$',
    '`': '\`',
}
ROOT_PATH = os.sep


class Rooted(object):
    def __init__(self, run_as_root):
        self.root_mode = run_as_root
        self.engaged = False

    def __enter__(self):
        if self.root_mode and not got_root():
            root_mode()
            self.engaged = True
        return self.engaged

    def __exit__(self, type, value, traceback):
        if self.root_mode and self.engaged:
            user_mode()
            self.engaged = False


def is_dry_run():
    dry_v = env.get_key('ANVIL_DRYRUN')
    if not dry_v:
        return False
    return tu.make_bool(dry_v)


def execute(*cmd, **kwargs):
    process_input = kwargs.pop('process_input', None)
    check_exit_code = kwargs.pop('check_exit_code', [0])
    cwd = kwargs.pop('cwd', None)
    env_overrides = kwargs.pop('env_overrides', None)
    close_stdin = kwargs.pop('close_stdin', False)
    ignore_exit_code = kwargs.pop('ignore_exit_code', False)

    if isinstance(check_exit_code, bool):
        ignore_exit_code = not check_exit_code
        check_exit_code = [0]
    elif isinstance(check_exit_code, int):
        check_exit_code = [check_exit_code]

    run_as_root = kwargs.pop('run_as_root', False)
    shell = kwargs.pop('shell', False)

    # Ensure all string args
    execute_cmd = []
    for c in cmd:
        execute_cmd.append(str(c))

    # From the docs it seems a shell command must be a string??
    # TODO(harlowja) this might not really be needed?
    str_cmd = " ".join(execute_cmd)
    if shell:
        execute_cmd = str_cmd.strip()

    stdin_fh = subprocess.PIPE
    stdout_fh = subprocess.PIPE
    stderr_fh = subprocess.PIPE
    close_file_descriptors = True

    if 'stdout_fh' in kwargs.keys():
        stdout_fh = kwargs.get('stdout_fh')

    if 'stdin_fh' in kwargs.keys():
        stdin_fh = kwargs.get('stdin_fh')
        process_input = None

    if 'stderr_fh' in kwargs.keys():
        stderr_fh = kwargs.get('stderr_fh')

    if not shell:
        LOG.debug('Running cmd: %r' % (execute_cmd))
    else:
        LOG.debug('Running shell cmd: %r' % (execute_cmd))
    if process_input is not None:
        LOG.debug('With stdin: %s' % (process_input))
    if cwd:
        LOG.debug("In working directory: %r" % (cwd))

    process_env = None
    if env_overrides and len(env_overrides):
        process_env = env.get()
        for (k, v) in env_overrides.items():
            process_env[k] = str(v)
    else:
        process_env = env.get()

    # LOG.debug("With environment %s", process_env)
    demoter = None

    def demoter_functor(user_uid, user_gid):
        def doit():
            os.setregid(user_gid, user_gid)
            os.setreuid(user_uid, user_uid)
        return doit

    if not run_as_root:
        (user_uid, user_gid) = get_suids()
        if user_uid is None or user_gid is None:
            pass
        else:
            demoter = demoter_functor(user_uid=user_uid, user_gid=user_gid)

    rc = None
    result = None
    with Rooted(run_as_root):
        if is_dry_run():
            rc = 0
            result = ('', '')
        else:
            try:
                obj = subprocess.Popen(execute_cmd, stdin=stdin_fh, stdout=stdout_fh, stderr=stderr_fh,
                                       close_fds=close_file_descriptors, cwd=cwd, shell=shell,
                                       preexec_fn=demoter, env=process_env)
                if process_input is not None:
                    result = obj.communicate(str(process_input))
                else:
                    result = obj.communicate()
            except OSError as e:
                raise excp.ProcessExecutionError(description="%s: [%s, %s]" % (e, e.errno, e.strerror),
                                                 cmd=str_cmd)
            if (stdin_fh != subprocess.PIPE and obj.stdin and close_stdin):
                obj.stdin.close()
            rc = obj.returncode

    if not result:
        result = ("", "")

    (stdout, stderr) = result
    if stdout is None:
        stdout = ''
    if stderr is None:
        stderr = ''

    if (not ignore_exit_code) and (rc not in check_exit_code):
        raise excp.ProcessExecutionError(exit_code=rc, stdout=stdout,
                                         stderr=stderr, cmd=str_cmd)
    else:
        # Log it anyway
        if rc not in check_exit_code:
            LOG.debug("A failure may of just happened when running command %r [%s] (%s, %s)",
                      str_cmd, rc, stdout, stderr)
        # See if a requested storage place was given for stderr/stdout
        trace_writer = kwargs.get('trace_writer')
        stdout_fn = kwargs.get('stdout_fn')
        if stdout_fn:
            write_file(stdout_fn, stdout)
            if trace_writer:
                trace_writer.file_touched(stdout_fn)
        stderr_fn = kwargs.get('stderr_fn')
        if stderr_fn:
            write_file(stderr_fn, stderr)
            if trace_writer:
                trace_writer.file_touched(stderr_fn)
        return (stdout, stderr)


def abspth(path):
    if not path:
        path = ROOT_PATH
    if path == "~":
        path = gethomedir()
    return os.path.abspath(path)


def hostname():
    try:
        return socket.gethostname()
    except socket.error:
        return 'localhost'


def isuseable(path, options=os.W_OK | os.R_OK | os.X_OK):
    return os.access(path, options)


def pipe_in_out(in_fh, out_fh, chunk_size=1024, chunk_cb=None):
    bytes_piped = 0
    LOG.debug("Transferring the contents of %s to %s in chunks of size %s.", in_fh, out_fh, chunk_size)
    while True:
        data = in_fh.read(chunk_size)
        if data == '':
            break
        else:
            out_fh.write(data)
            bytes_piped += len(data)
            if chunk_cb:
                chunk_cb(bytes_piped)
    return bytes_piped


def shellquote(text):
    # TODO(harlowja) find a better way - since there doesn't seem to be a standard lib that actually works
    do_adjust = False
    for srch in SHELL_QUOTE_REPLACERS.keys():
        if text.find(srch) != -1:
            do_adjust = True
            break
    if do_adjust:
        for (srch, replace) in SHELL_QUOTE_REPLACERS.items():
            text = text.replace(srch, replace)
    if do_adjust or \
        text.startswith((" ", "\t")) or \
        text.endswith((" ", "\t")) or \
        text.find("'") != -1:
        text = "\"%s\"" % (text)
    return text


def fileperms(path):
    return (os.stat(path).st_mode & 0777)


def listdir(path):
    return os.listdir(path)


def isfile(fn):
    return os.path.isfile(fn)


def isdir(path):
    return os.path.isdir(path)


def islink(path):
    return os.path.islink(path)


def joinpths(*paths):
    return os.path.join(*paths)


def get_suids():
    uid = env.get_key('SUDO_UID')
    if uid is not None:
        uid = int(uid)
    gid = env.get_key('SUDO_GID')
    if gid is not None:
        gid = int(gid)
    return (uid, gid)


def chown(path, uid, gid, run_as_root=True):
    LOG.debug("Changing ownership of %r to %s:%s" % (path, uid, gid))
    with Rooted(run_as_root):
        if not is_dry_run():
            os.chown(path, uid, gid)
    return 1


def chown_r(path, uid, gid, run_as_root=True):
    changed = 0
    with Rooted(run_as_root):
        if isdir(path):
            for (root, dirs, files) in os.walk(path):
                changed += chown(root, uid, gid)
                for d in dirs:
                    dir_pth = joinpths(root, d)
                    changed += chown(dir_pth, uid, gid)
                for f in files:
                    fn_pth = joinpths(root, f)
                    changed += chown(fn_pth, uid, gid)
    return changed


def _explode_path(path):
    dirs = []
    comps = []
    path = abspth(path)
    dirs.append(path)
    (head, tail) = os.path.split(path)
    while tail:
        dirs.append(head)
        comps.append(tail)
        path = head
        (head, tail) = os.path.split(path)
    dirs.sort()
    comps.reverse()
    return (dirs, comps)


def explode_path(path):
    return _explode_path(path)[0]


def _attempt_kill(pid, signal_type, max_try, wait_time):
    killed = False
    attempts = 0
    for _i in range(0, max_try):
        try:
            LOG.debug("Attempting to kill pid %s" % (pid))
            attempts += 1
            os.kill(pid, signal_type)
            LOG.debug("Sleeping for %s seconds before next attempt to kill pid %s" % (wait_time, pid))
            sleep(wait_time)
        except OSError as e:
            if e.errno == errno.ESRCH:
                killed = True
                break
            else:
                LOG.debug("Sleeping for %s seconds before next attempt to kill pid %s" % (wait_time, pid))
                sleep(wait_time)
    return (killed, attempts)


def kill(pid, max_try=4, wait_time=1):
    if not is_running(pid) or is_dry_run():
        return (True, 0)
    (killed, i_attempts) = _attempt_kill(pid, signal.SIGINT, int(max_try / 2), wait_time)
    if killed:
        return (True, i_attempts)
    (killed, k_attempts) = _attempt_kill(pid, signal.SIGKILL, int(max_try / 2), wait_time)
    if killed:
        return (True, i_attempts + k_attempts)
    else:
        return (False, i_attempts + k_attempts)


def fork(program, app_dir, pid_fn, stdout_fn, stderr_fn, *args):
    if is_dry_run():
        return
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
            (_soft, hard) = resource.getrlimit(resource.RLIMIT_NOFILE)
            mkfd = hard
            if mkfd == resource.RLIM_INFINITY:
                mkfd = 2048  # Is this defined anywhere??
            for fd in range(0, mkfd):
                try:
                    os.close(fd)
                except OSError:
                    # Not open, thats ok
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
            prog_little = basename(program)
            actualargs = [prog_little] + list(args)
            os.execlp(program, *actualargs)
        else:
            # Write out the child pid
            contents = "%s\n" % (pid)
            write_file(pid_fn, contents, quiet=True)
            # Not exit or sys.exit, this is recommended
            # since it will do the right cleanups that we want
            # not calling any atexit functions, which would
            # be bad right now
            os._exit(0)


def is_running(pid):
    if is_dry_run():
        return True
    # Check proc
    proc_fn = joinpths("/proc", str(pid))
    if exists(proc_fn):
        LOG.debug("By looking at %s we determined %s is still running.", proc_fn, pid)
        return True
    # Try a slightly more aggressive way...
    running = True
    try:
        os.kill(pid, 0)
    except OSError as e:
        if e.errno == errno.EPERM:
            pass
        else:
            running = False
    LOG.debug("By attempting to signal %s we determined it is %s", pid, {True: 'alive', False: 'dead'}[running])
    return running


def mkdirslist(path):
    dirs_possible = explode_path(path)
    dirs_made = []
    for check_path in dirs_possible:
        if not isdir(check_path):
            mkdir(check_path, False)
            dirs_made.append(check_path)
    return dirs_made


def append_file(fn, text, flush=True, quiet=False):
    if not quiet:
        LOG.debug("Appending to file %r (%d bytes) (flush=%s)", fn, len(text), (flush))
        LOG.debug(">> %s" % (text))
    if not is_dry_run():
        with open(fn, "a") as f:
            f.write(text)
            if flush:
                f.flush()
    return fn


def write_file(fn, text, flush=True, quiet=False):
    if not quiet:
        LOG.debug("Writing to file %r (%d bytes) (flush=%s)", fn, len(text), (flush))
        LOG.debug("> %s" % (text))
    if not is_dry_run():
        with open(fn, "w") as f:
            f.write(text)
            if flush:
                f.flush()
    return fn


def touch_file(fn, die_if_there=True, quiet=False, file_size=0):
    if not isfile(fn):
        if not quiet:
            LOG.debug("Touching and truncating file %r (truncate size=%s)", fn, file_size)
        if not is_dry_run():
            with open(fn, "w") as f:
                f.truncate(file_size)
    else:
        if die_if_there:
            msg = "Can not touch & truncate file %r since it already exists" % (fn)
            raise excp.FileException(msg)
    return fn


def load_file(fn):
    data = ""
    if not is_dry_run():
        with open(fn, "r") as f:
            data = f.read()
    return data


def mkdir(path, recurse=True):
    if not isdir(path):
        if recurse:
            LOG.debug("Recursively creating directory %r" % (path))
            if not is_dry_run():
                os.makedirs(path)
        else:
            LOG.debug("Creating directory %r" % (path))
            if not is_dry_run():
                os.mkdir(path)
    return path


def deldir(path, run_as_root=False):
    with Rooted(run_as_root):
        if isdir(path):
            LOG.debug("Recursively deleting directory tree starting at %r" % (path))
            if not is_dry_run():
                shutil.rmtree(path)


def rmdir(path, quiet=True, run_as_root=False):
    if not isdir(path):
        return
    try:
        with Rooted(run_as_root):
            LOG.debug("Deleting directory %r with the cavet that we will fail if it's not empty." % (path))
            if not is_dry_run():
                os.rmdir(path)
            LOG.debug("Deleted directory %r" % (path))
    except OSError:
        if not quiet:
            raise
        else:
            pass


def symlink(source, link, force=True, run_as_root=True):
    with Rooted(run_as_root):
        LOG.debug("Creating symlink from %r => %r" % (link, source))
        path = dirname(link)
        needed_pths = mkdirslist(path)
        if not is_dry_run():
            if force and (exists(link) or islink(link)):
                unlink(link, True)
            os.symlink(source, link)
        return needed_pths


def exists(path):
    return os.path.exists(path)


def basename(path):
    return os.path.basename(path)


def dirname(path):
    return os.path.dirname(path)


def canon_path(path):
    return os.path.realpath(path)


def prompt(prompt_str):
    return raw_input(prompt_str)


def user_exists(username):
    all_users = pwd.getpwall()
    for info in all_users:
        if info.pw_name == username:
            return True
    return False


def group_exists(grpname):
    all_grps = grp.getgrall()
    for info in all_grps:
        if info.gr_name == grpname:
            return True
    return False


def getuser():
    (uid, _gid) = get_suids()
    if uid is None:
        return getpass.getuser()
    return pwd.getpwuid(uid).pw_name


def getuid(username):
    return pwd.getpwnam(username).pw_uid


def gethomedir(user=None):
    if not user:
        user = getuser()
    home_dir = os.path.expanduser("~%s" % (user))
    return home_dir


def getgid(groupname):
    return grp.getgrnam(groupname).gr_gid


def getgroupname():
    (_uid, gid) = get_suids()
    if gid is None:
        gid = os.getgid()
    return grp.getgrgid(gid).gr_name


def unlink(path, ignore_errors=True, run_as_root=False):
    LOG.debug("Unlinking (removing) %r" % (path))
    if not is_dry_run():
        try:
            with Rooted(run_as_root):
                os.unlink(path)
        except OSError:
            if not ignore_errors:
                raise
            else:
                pass


def copy(src, dst):
    LOG.debug("Copying: %r => %r" % (src, dst))
    if not is_dry_run():
        shutil.copy(src, dst)
    return dst


def copytree(src, dst):
    LOG.debug("Copying full tree: %r => %r" % (src, dst))
    if not is_dry_run():
        shutil.copytree(src, dst)
    return dst


def move(src, dst):
    LOG.debug("Moving: %r => %r" % (src, dst))
    if not is_dry_run():
        shutil.move(src, dst)
    return dst


def write_file_and_backup(path, contents, bk_ext='org'):
    perms = None
    backup_path = None
    if isfile(path):
        perms = fileperms(path)
        backup_path = "%s.%s" % (path, bk_ext)
        if not isfile(backup_path):
            LOG.debug("Backing up %s => %s", path, backup_path)
            move(path, backup_path)
        else:
            LOG.debug("Leaving original backup of %s at %s", path, backup_path)
    write_file(path, contents)
    if perms is not None:
        chmod(path, perms)
    return backup_path


def chmod(fname, mode):
    LOG.debug("Applying chmod: %r to %o" % (fname, mode))
    if not is_dry_run():
        os.chmod(fname, mode)
    return fname


def got_root():
    return (os.geteuid() == 0)


def root_mode(quiet=True):
    root_uid = getuid('root')
    root_gid = getgid('root')
    if root_uid is None or root_gid is None:
        msg = "Cannot escalate permissions to (user=root) - does that user exist??"
        if quiet:
            LOG.warn(msg)
        else:
            raise excp.AnvilException(msg)
    else:
        try:
            os.setreuid(0, root_uid)
            os.setregid(0, root_gid)
        except OSError:
            if quiet:
                LOG.warn("Cannot escalate permissions to (user=%s, group=%s)" % (root_uid, root_gid))
            else:
                raise


def user_mode(quiet=True):
    (sudo_uid, sudo_gid) = get_suids()
    if sudo_uid is not None and sudo_gid is not None:
        try:
            os.setregid(0, sudo_gid)
            os.setreuid(0, sudo_uid)
        except OSError:
            if quiet:
                LOG.warn("Cannot drop permissions to (user=%s, group=%s)" % (sudo_uid, sudo_gid))
            else:
                raise
    else:
        msg = "Can not switch to user mode, no suid user id or group id"
        if quiet:
            LOG.warn(msg)
        else:
            raise excp.AnvilException(msg)


def is_executable(fn):
    return isfile(fn) and os.access(fn, os.X_OK)


def geteuid():
    return os.geteuid()


def getegid():
    return os.getegid()


def sleep(winks):
    if winks <= 0:
        return
    if is_dry_run():
        LOG.debug("Not really sleeping for: %s seconds" % (winks))
    else:
        time.sleep(winks)
