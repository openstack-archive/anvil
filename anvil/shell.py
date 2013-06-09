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

# R0915: Too many statements
# pylint: disable=R0915

import distutils.spawn
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

import psutil  # http://code.google.com/p/psutil/wiki/Documentation

import anvil
from anvil import env
from anvil import exceptions as excp
from anvil import log as logging

LOG = logging.getLogger(__name__)

# Locally stash these so that they can not be changed
# by others after this is first fetched...
SUDO_UID = env.get_key('SUDO_UID')
SUDO_GID = env.get_key('SUDO_GID')

# Set only once
IS_DRYRUN = None


class Process(psutil.Process):
    def __str__(self):
        return "%s (%s)" % (self.pid, self.name)


def set_dry_run(on_off):
    global IS_DRYRUN
    if not isinstance(on_off, (bool)):
        raise TypeError("Dry run value must be a boolean")
    if IS_DRYRUN is not None:
        raise RuntimeError("Dry run value has already been previously set to '%s'" % (IS_DRYRUN))
    IS_DRYRUN = on_off


def is_dry_run():
    return bool(IS_DRYRUN)


# Originally borrowed from nova computes execute...
def execute(cmd,
            process_input=None,
            check_exit_code=True,
            cwd=None,
            shell=False,
            env_overrides=None,
            stdout_fh=None,
            stderr_fh=None,
            stdout_fn=None,
            stderr_fn=None,
            trace_writer=None):
    """Helper method to execute command.

    :param cmd:             Passed to subprocess.Popen
    :param process_input:   Send to opened process
    :param check_exit_code: Single `bool`, `int`, or `list` of allowed exit
                            codes.  By default, only 0 exit code is allowed.
                            Raise :class:`exceptions.ProcessExecutionError`
                            unless program exits with one of these code

    :returns: a tuple, (stdout, stderr) from the spawned process, or None if
              the command fails
    """
    if isinstance(check_exit_code, (bool)):
        ignore_exit_code = not check_exit_code
        check_exit_code = [0]
    elif isinstance(check_exit_code, (int)):
        check_exit_code = [check_exit_code]

    # Ensure all string args (ie for those that send ints and such...)
    execute_cmd = [str(c) for c in cmd]

    # From the docs it seems a shell command must be a string??
    # TODO(harlowja) this might not really be needed?
    str_cmd = " ".join(shellquote(word) for word in cmd)

    if shell:
        execute_cmd = str_cmd

    if not shell:
        LOG.debug('Running cmd: %r' % (execute_cmd))
    else:
        LOG.debug('Running shell cmd: %r' % (execute_cmd))

    if process_input is not None:
        LOG.debug('With stdin: %s' % (process_input))
    if cwd:
        LOG.debug("In working directory: %r" % (cwd))

    if stdout_fn is not None and stdout_fh is not None:
        LOG.warn("Stdout file handles and stdout file names can not be used simultaneously!")
    if stderr_fn is not None and stderr_fh is not None:
        LOG.warn("Stderr file handles and stderr file names can not be used simultaneously!")

    process_env = None
    if env_overrides and len(env_overrides):
        process_env = env.get()
        for (k, v) in env_overrides.items():
            process_env[k] = str(v)

    rc = None
    result = ("", "")
    if is_dry_run():
        rc = 0
    else:
        stdin_fh = subprocess.PIPE
        if stdout_fn or (stdout_fh is None):
            stdout_fh = subprocess.PIPE
        if stderr_fn or (stderr_fh is None):
            stderr_fh = subprocess.PIPE
        try:
            obj = subprocess.Popen(execute_cmd, stdin=stdin_fh, stdout=stdout_fh, stderr=stderr_fh,
                                   close_fds=True, cwd=cwd, shell=shell,
                                   env=process_env)
            if process_input is not None:
                result = obj.communicate(str(process_input))
            else:
                result = obj.communicate()
        except OSError as e:
            raise excp.ProcessExecutionError(description="%s: [%s, %s]" % (e, e.errno, e.strerror),
                                             cmd=str_cmd)
        rc = obj.returncode

    if stdout_fh != subprocess.PIPE:
        stdout = "<redirected to %s>" % (stdout_fn or stdout_fh)
    else:
        stdout = result[0] or ""
    if stderr_fh != subprocess.PIPE:
        stderr = "<redirected to %s>" % (stderr_fn or stderr_fh)
    else:
        stderr = result[1] or ""

    if (not ignore_exit_code) and (rc not in check_exit_code):
        raise excp.ProcessExecutionError(exit_code=rc, stdout=stdout,
                                         stderr=stderr, cmd=str_cmd)
    else:
        # Log it anyway
        if rc not in check_exit_code:
            LOG.debug("A failure may of just happened when running command %r [%s] (%s, %s)",
                      str_cmd, rc, stdout, stderr)
        # See if a requested storage place was given for stderr/stdout
        for name, handle in ((stdout_fn, stdout), (stderr_fn, stderr)):
            if name:
                write_file(name, handle)
                if trace_writer:
                    trace_writer.file_touched(name)
        return (stdout, stderr)


def execute_save_output(cmd, out_filename, **kwargs):
    kwargs = kwargs.copy()
    mkdirslist(dirname(out_filename))
    quiet = kwargs.pop('quiet', False)
    log_how = LOG.info
    if quiet:
        log_how = LOG.debug
    log_how("You can watch progress in another terminal with")
    log_how("    tail -f %s" % out_filename)
    with open(out_filename, "w") as out:
        kwargs["stdout_fh"] = out
        kwargs["stderr_fh"] = out
        execute(cmd, **kwargs)


def abspth(path):
    if not path:
        path = "/"
    if path == "~":
        path = gethomedir()
    return os.path.abspath(path)


def hostname(default='localhost'):
    try:
        return socket.gethostname()
    except socket.error:
        return default


def isuseable(path, options=os.W_OK | os.R_OK | os.X_OK):
    return os.access(path, options)


# Useful for doing progress bars that get told the current progress
# for the transfer ever chunk via the chunk callback function that
# will be called after each chunk has been written...
def pipe_in_out(in_fh, out_fh, chunk_size=1024, chunk_cb=None):
    bytes_piped = 0
    LOG.debug("Transferring the contents of %s to %s in chunks of size %s.", in_fh, out_fh, chunk_size)
    while True:
        data = in_fh.read(chunk_size)
        if data == '':
            # EOF
            break
        else:
            out_fh.write(data)
            bytes_piped += len(data)
            if chunk_cb:
                chunk_cb(bytes_piped)
    return bytes_piped


def shellquote(text):
    if text.isalnum():
        return text
    return "'%s'" % text.replace("'", "'\\''")


def fileperms(path):
    return (os.stat(path).st_mode & 0777)


def listdir(path, recursive=False, dirs_only=False, files_only=False):
    path = abspth(path)
    all_contents = []
    if not recursive:
        all_contents = os.listdir(path)
        all_contents = [os.path.join(path, f) for f in all_contents]
    else:
        for (root, dirs, files) in os.walk(path):
            for d in dirs:
                all_contents.append(joinpths(root, d))
            for f in files:
                all_contents.append(joinpths(root, f))
    if dirs_only:
        all_contents = [f for f in all_contents if isdir(f)]
    if files_only:
        all_contents = [f for f in all_contents if isfile(f)]
    return all_contents


def isfile(fn):
    return os.path.isfile(fn)


def isdir(path):
    return os.path.isdir(path)


def islink(path):
    return os.path.islink(path)


def joinpths(*paths):
    return os.path.join(*paths)


def get_suids():
    uid = SUDO_UID
    if uid is not None:
        uid = int(uid)
    gid = SUDO_GID
    if gid is not None:
        gid = int(gid)
    return (uid, gid)


def chown(path, uid, gid):
    if uid is None:
        uid = -1
    if gid is None:
        gid = -1
    if uid == -1 and gid == -1:
        return 0
    LOG.debug("Changing ownership of %r to %s:%s" % (path, uid, gid))
    if not is_dry_run():
        os.chown(path, uid, gid)
    return 1


def chown_r(path, uid, gid):
    changed = 0
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


def _attempt_kill(proc, signal_type, max_try, wait_time):
    try:
        if not proc.is_running():
            return (True, 0)
    except psutil.error.NoSuchProcess:
        return (True, 0)
    # Be a little more forceful...
    killed = False
    attempts = 0
    for _i in range(0, max_try):
        try:
            LOG.debug("Attempting to kill process %s" % (proc))
            attempts += 1
            proc.send_signal(signal_type)
            LOG.debug("Sleeping for %s seconds before next attempt to kill process %s" % (wait_time, proc))
            sleep(wait_time)
        except psutil.error.NoSuchProcess:
            killed = True
            break
        except Exception as e:
            LOG.debug("Failed killing %s due to: %s", proc, e)
            LOG.debug("Sleeping for %s seconds before next attempt to kill process %s" % (wait_time, proc))
            sleep(wait_time)
    return (killed, attempts)


def kill(pid, max_try=4, wait_time=1):
    if not is_running(pid) or is_dry_run():
        return (True, 0)
    proc = Process(pid)
    # Try the nicer sig-int first...
    (killed, i_attempts) = _attempt_kill(proc, signal.SIGINT, int(max_try / 2), wait_time)
    if killed:
        return (True, i_attempts)
    # Get agressive and try sig-kill....
    (killed, k_attempts) = _attempt_kill(proc, signal.SIGKILL, int(max_try / 2), wait_time)
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
    try:
        return Process(pid).is_running()
    except psutil.error.NoSuchProcess:
        return False


def mkdirslist(path, tracewriter=None):
    dirs_possible = explode_path(path)
    dirs_made = []
    for dir_path in dirs_possible:
        if not isdir(dir_path):
            mkdir(dir_path, recurse=False)
            if tracewriter:
                tracewriter.dirs_made(dir_path)
            dirs_made.append(dir_path)
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


def write_file(fn, text, flush=True, quiet=False, tracewriter=None):
    if not quiet:
        LOG.debug("Writing to file %r (%d bytes) (flush=%s)", fn, len(text), (flush))
        LOG.debug("> %s" % (text))
    if not is_dry_run():
        mkdirslist(dirname(fn), tracewriter=tracewriter)
        with open(fn, "w") as fh:
            fh.write(text)
            if flush:
                fh.flush()
    if tracewriter:
        tracewriter.file_touched(fn)


def touch_file(fn, die_if_there=True, quiet=False, file_size=0, tracewriter=None):
    if not isfile(fn):
        if not quiet:
            LOG.debug("Touching and truncating file %r (truncate size=%s)", fn, file_size)
        if not is_dry_run():
            mkdirslist(dirname(fn), tracewriter=tracewriter)
            with open(fn, "w") as fh:
                fh.truncate(file_size)
            if tracewriter:
                tracewriter.file_touched(fn)
    else:
        if die_if_there:
            msg = "Can not touch & truncate file %r since it already exists" % (fn)
            raise excp.FileException(msg)


def load_file(fn):
    data = ""
    if not is_dry_run():
        with open(fn, "r") as fh:
            data = fh.read()
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


def deldir(path):
    if isdir(path):
        LOG.debug("Recursively deleting directory tree starting at %r" % (path))
        if not is_dry_run():
            shutil.rmtree(path)


def rmdir(path, quiet=True):
    if not isdir(path):
        return
    try:
        LOG.debug("Deleting directory %r with the cavet that we will fail if it's not empty." % (path))
        if not is_dry_run():
            os.rmdir(path)
        LOG.debug("Deleted directory %r" % (path))
    except OSError:
        if not quiet:
            raise
        else:
            pass


def symlink(source, link, force=True, tracewriter=None):
    LOG.debug("Creating symlink from %r => %r" % (link, source))
    mkdirslist(dirname(link), tracewriter=tracewriter)
    if not is_dry_run():
        if force and (exists(link) and islink(link)):
            unlink(link, True)
        os.symlink(source, link)
        if tracewriter:
            tracewriter.symlink_made(link)


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


def unlink(path, ignore_errors=True):
    LOG.debug("Unlinking (removing) %r" % (path))
    if not is_dry_run():
        try:
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


def move(src, dst, force=False):
    LOG.debug("Moving: %r => %r" % (src, dst))
    if not is_dry_run():
        if force:
            if isdir(dst):
                dst = joinpths(dst, basename(src))
            if isfile(dst):
                unlink(dst)
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
    e_id = geteuid()
    g_id = getegid()
    for a_id in [e_id, g_id]:
        if a_id != 0:
            return False
    return True


def root_mode(quiet=True):
    root_uid = 0
    root_gid = 0
    try:
        os.setreuid(0, root_uid)
        os.setregid(0, root_gid)
    except OSError as e:
        msg = "Cannot escalate permissions to (uid=%s, gid=%s): %s" % (root_uid, root_gid, e)
        if quiet:
            LOG.warn(msg)
        else:
            raise excp.PermException(msg)


def is_executable(fn):
    return isfile(fn) and isuseable(fn, options=os.X_OK)


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


def which(name, additional_dirs=None):
    full_name = distutils.spawn.find_executable(name)
    if full_name:
        return full_name
    for dir_name in additional_dirs or []:
        full_name = joinpths(
            dirname(dirname(abspth(anvil.__file__))),
            dir_name,
            name)
        if isfile(full_name):
            return full_name
    raise excp.FileException("Cannot find %s" % name)
