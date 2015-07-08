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

import collections
import contextlib
import getpass
import grp
import gzip as gz
import os
import pwd
import shutil
import signal
import socket
import subprocess
import time

import distutils.spawn

import psutil

import anvil
from anvil import env
from anvil import exceptions as excp
from anvil import log as logging

LOG = logging.getLogger(__name__)


# Locally stash these so that they can not be changed
# by others after this is first fetched...
SUDO_UID = env.get_key('SUDO_UID')
SUDO_GID = env.get_key('SUDO_GID')

# Tail this many lines from a file when executed and output is being
# piped to said file.
_TRUNCATED_OUTPUT_LINES = 7

# Take over some functions directly from os.path/os/... so that we don't have
# to type as many long function names to access these.
getsize = os.path.getsize
exists = os.path.exists
basename = os.path.basename
dirname = os.path.dirname
canon_path = os.path.realpath
prompt = raw_input
isfile = os.path.isfile
isdir = os.path.isdir
islink = os.path.islink
geteuid = os.geteuid
getegid = os.getegid


class Process(psutil.Process):
    def __str__(self):
        return "%s (%s)" % (self.pid, self.name)


# Originally borrowed from nova compute execute.
def execute(cmd,
            process_input=None,
            check_exit_code=True,
            cwd=None,
            shell=False,
            env_overrides=None,
            stdout_fh=subprocess.PIPE,
            stderr_fh=subprocess.PIPE):
    """Helper method to execute a command through subprocess.

    :param cmd:             Command passed to subprocess.Popen.
    :param process_input:   Input send to opened process.
    :param check_exit_code: Specifies whether to check process return code.
                            If return code is other then `0` - exception will
                            be raised.
    :param cwd:             The child's current directory will be changed to
                            `cwd` before it is executed.
    :param shell:           Specifies whether to use the shell as the program
                            to execute.
    :param env_overrides:   Process environment parameters to override.
    :param stdout_fh:       Stdout file handler.
    :param stderr_fh:       Stderr file handler.
    :returns:               A tuple, (stdout, stderr) from the spawned process.
    :raises:                :class:`exceptions.ProcessExecutionError` when
                            process ends with other then `0` return code.
    """
    # Ensure all string args (i.e. for those that send ints, etc.).
    cmd = map(str, cmd)

    # NOTE(skudriashev): If shell is True, it is recommended to pass args as a
    # string rather than as a sequence.
    str_cmd = subprocess.list2cmdline(cmd)
    if shell:
        cmd = str_cmd
        LOG.debug('Running shell cmd: %r' % cmd)
    else:
        LOG.debug('Running cmd: %r' % cmd)

    if process_input is not None:
        process_input = str(process_input)
        LOG.debug('Process input: %s' % process_input)

    if cwd:
        LOG.debug('Process working directory: %r' % cwd)

    # Override process environment in needed.
    process_env = None
    if env_overrides and len(env_overrides):
        process_env = env.get()
        for k, v in env_overrides.items():
            LOG.debug("Using environment override '%s' => '%s'", k, v)
            process_env[k] = str(v)

    # Run command process.
    exec_kwargs = {
        'stdin': subprocess.PIPE,
        'stdout': stdout_fh,
        'stderr': stderr_fh,
        'close_fds': True,
        'shell': shell,
        'cwd': cwd,
        'env': process_env,
    }
    result = ("", "")
    try:
        obj = subprocess.Popen(cmd, **exec_kwargs)
        result = obj.communicate(process_input)
    except OSError as e:
        raise excp.ProcessExecutionError(
            str_cmd,
            exec_kwargs=exec_kwargs,
            description="%s: [%s, %s]" % (e, e.errno, e.strerror)
        )
    else:
        rc = obj.returncode

    # Handle process exit code.
    stdout = result[0] or ""
    stderr = result[1] or ""
    if rc != 0 and check_exit_code:
        # Raise exception if return code is not `0`.
        e = excp.ProcessExecutionError(str_cmd,
                                       exec_kwargs=exec_kwargs,
                                       stdout=stdout,
                                       stderr=stderr,
                                       exit_code=rc,
                                       where_output="debug log")
        LOG.debug("Stdout: %s", e.stdout)
        LOG.debug("Stderr: %s", e.stderr)
        raise e
    return stdout, stderr


def execute_save_output(cmd, file_name, **kwargs):
    """Helper method to execute a command through subprocess and save stdout
    and stderr into a file.
    """
    kwargs = kwargs.copy()
    mkdirslist(dirname(file_name))
    try:
        with open(file_name, 'wb') as fh:
            return execute(cmd, stdout_fh=fh, stderr_fh=fh, **kwargs)
    except excp.ProcessExecutionError:
        with excp.reraise():
            try:
                with open(file_name, 'rb') as fh:
                    lines = collections.deque(fh,
                                              maxlen=_TRUNCATED_OUTPUT_LINES)
                content = "".join(lines)
            except IOError:
                pass
            else:
                LOG.debug('Last lines from %s:\n%s', file_name, content)


@contextlib.contextmanager
def remove_before(path):
    if isdir(path):
        deldir(path)
    if isfile(path):
        unlink(path)
    yield path


def gzip(file_name, gz_archive_name=None):
    if not isfile(file_name):
        raise IOError("Can not gzip non-existent file: %s" % (file_name))
    if not gz_archive_name:
        gz_archive_name = "%s.gz" % (file_name)
    with contextlib.closing(gz.open(gz_archive_name, 'wb')) as tz:
        with open(file_name, 'rb') as fh:
            tz.write(fh.read())
        return gz_archive_name


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


def fileperms(path):
    return (os.stat(path).st_mode & 0o777)


def listdir(path, recursive=False, dirs_only=False, files_only=False, filter_func=None):
    path = abspth(path)
    all_contents = []
    if not recursive:
        all_contents = os.listdir(path)
        all_contents = [joinpths(path, f) for f in all_contents]
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
    if filter_func:
        all_contents = [f for f in all_contents if filter_func(f)]
    return all_contents


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
    if not is_running(pid):
        return (True, 0)
    proc = Process(pid)
    # Try the nicer sig-int first.
    (killed, i_attempts) = _attempt_kill(proc, signal.SIGINT,
                                         int(max_try / 2), wait_time)
    if killed:
        return (True, i_attempts)
    # Get aggressive and try sig-kill.
    (killed, k_attempts) = _attempt_kill(proc, signal.SIGKILL,
                                         int(max_try / 2), wait_time)
    return (killed, i_attempts + k_attempts)


def is_running(pid):
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
    with open(fn, "a") as f:
        f.write(text)
        if flush:
            f.flush()
    return fn


def write_file(fn, text, flush=True, quiet=False, tracewriter=None):
    if not quiet:
        LOG.debug("Writing to file %r (%d bytes) (flush=%s)", fn, len(text), (flush))
        LOG.debug("> %s" % (text))
    mkdirslist(dirname(fn), tracewriter=tracewriter)
    with open(fn, "w") as fh:
        if isinstance(text, unicode):
            text = text.encode("utf-8")
        fh.write(text)
        if flush:
            fh.flush()
    if tracewriter:
        tracewriter.file_touched(fn)


def touch_file(fn, die_if_there=True, quiet=False, file_size=0, tracewriter=None):
    if not isfile(fn):
        if not quiet:
            LOG.debug("Touching and truncating file %r (truncate size=%s)", fn, file_size)
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
    with open(fn, "rb") as fh:
        return fh.read()


def mkdir(path, recurse=True):
    if not isdir(path):
        if recurse:
            LOG.debug("Recursively creating directory %r" % (path))
            os.makedirs(path)
        else:
            LOG.debug("Creating directory %r" % (path))
            os.mkdir(path)
    return path


def deldir(path):
    if isdir(path):
        LOG.debug("Recursively deleting directory tree starting at %r" % (path))
        shutil.rmtree(path)


def rmdir(path, quiet=True):
    if not isdir(path):
        return
    try:
        LOG.debug("Deleting directory %r with the cavet that we will fail if it's not empty." % (path))
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
    if force and (exists(link) and islink(link)):
        unlink(link, True)
    os.symlink(source, link)
    if tracewriter:
        tracewriter.symlink_made(link)


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
    try:
        os.unlink(path)
    except OSError:
        if not ignore_errors:
            raise
        else:
            pass


def copy(src, dst, tracewriter=None):
    LOG.debug("Copying: %r => %r" % (src, dst))
    shutil.copy(src, dst)
    if tracewriter:
        tracewriter.file_touched(dst)
    return dst


def move(src, dst, force=False):
    LOG.debug("Moving: %r => %r" % (src, dst))
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
    os.chmod(fname, mode)
    return fname


def got_root():
    e_id = geteuid()
    g_id = getegid()
    for a_id in [e_id, g_id]:
        if a_id != 0:
            return False
    return True


def sleep(winks):
    if winks <= 0:
        return
    time.sleep(winks)


def which_first(bin_names, additional_dirs=None, ensure_executable=True):
    assert bin_names, 'Binary names required'
    for b in bin_names:
        try:
            return which(b,
                         additional_dirs=additional_dirs,
                         ensure_executable=ensure_executable)
        except excp.FileException:
            pass
    bin_names = ", ".join(bin_names)
    raise excp.FileException("Can't find any of %s" % bin_names)


def which(bin_name, additional_dirs=None, ensure_executable=True):

    def check_it(path):
        if not path:
            return False
        if not isfile(path):
            return False
        if ensure_executable and not os.access(path, os.X_OK):
            return False
        return True

    full_name = distutils.spawn.find_executable(bin_name)
    if check_it(full_name):
        return full_name
    if not additional_dirs:
        additional_dirs = []
    for dir_name in additional_dirs:
        full_name = joinpths(dirname(dirname(abspth(anvil.__file__))),
                             dir_name,
                             bin_name)
        if check_it(full_name):
            return full_name
    raise excp.FileException("Can't find %s" % bin_name)
