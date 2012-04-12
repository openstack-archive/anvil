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

import fileinput
import getpass
import grp
import os
import pwd
import shutil
import subprocess
import sys
import time

from devstack import env
from devstack import exceptions as excp
from devstack import log as logging

LOG = logging.getLogger("devstack.shell")
ROOT_USER = "root"
ROOT_USER_UID = 0
SUDO_UID = 'SUDO_UID'
SUDO_GID = 'SUDO_GID'
SHELL_QUOTE_REPLACERS = {
    "\"": "\\\"",
    "(": "\\(",
    ")": "\\)",
    "$": '\$',
    '`': '\`',
}
SHELL_WRAPPER = "\"%s\""
ROOT_PATH = os.sep
DRYRUN_MODE = False
DRY_RC = 0
DRY_STDOUT_ERR = ("", "")
BOOL2STR = {
    True: 'true',
    False: 'false',
}


def set_dryrun(val):
    global DRYRUN_MODE
    if val:
        LOG.debug("Setting dryrun to: %s" % (BOOL2STR.get(True)))
        DRYRUN_MODE = True
    else:
        LOG.debug("Resetting dryrun to: %s" % (BOOL2STR.get(False)))
        DRYRUN_MODE = False


#root context guard
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

    execute_cmd = list()
    for c in cmd:
        execute_cmd.append(str(c))

    str_cmd = " ".join(execute_cmd)
    if shell:
        execute_cmd = str_cmd.strip()

    if not shell:
        LOG.audit('Running cmd: %r' % (execute_cmd))
    else:
        LOG.audit('Running shell cmd: %r' % (execute_cmd))

    if process_input is not None:
        LOG.audit('With stdin: %s' % (process_input))

    if cwd:
        LOG.audit("In working directory: %r" % (cwd))

    stdin_fh = subprocess.PIPE
    stdout_fh = subprocess.PIPE
    stderr_fh = subprocess.PIPE
    close_file_descriptors = True

    if 'stdout_fh' in kwargs.keys():
        stdout_fh = kwargs.get('stdout_fh')
        LOG.debug("Redirecting stdout to file handle: %s" % (stdout_fh))

    if 'stdin_fh' in kwargs.keys():
        stdin_fh = kwargs.get('stdin_fh')
        LOG.debug("Redirecting stdin to file handle: %s" % (stdin_fh))
        process_input = None

    if 'stderr_fh' in kwargs.keys():
        stderr_fh = kwargs.get('stderr_fh')
        LOG.debug("Redirecting stderr to file handle: %s" % (stderr_fh))

    process_env = None
    if env_overrides and len(env_overrides):
        process_env = env.get()
        LOG.audit("With additional environment overrides: %s" % (env_overrides))
        for (k, v) in env_overrides.items():
            process_env[k] = str(v)

    rc = None
    result = None
    with Rooted(run_as_root):
        if DRYRUN_MODE:
            rc = DRY_RC
            result = DRY_STDOUT_ERR
        else:
            try:
                obj = subprocess.Popen(execute_cmd,
                                       stdin=stdin_fh,
                                       stdout=stdout_fh,
                                       stderr=stderr_fh,
                                       close_fds=close_file_descriptors,
                                       cwd=cwd,
                                       shell=shell,
                                       env=process_env)
                if process_input is not None:
                    result = obj.communicate(str(process_input))
                else:
                    result = obj.communicate()
            except OSError as e:
                raise excp.ProcessExecutionError(description="%s: [%s, %s]" % (e, e.errno, e.strerror),
                                                 cmd=str_cmd)
            if (stdin_fh != subprocess.PIPE
                and obj.stdin and close_stdin):
                obj.stdin.close()
            rc = obj.returncode
        LOG.audit('Cmd result had exit code: %s' % rc)

    if not result:
        result = ("", "")

    (stdout, stderr) = result
    if stdout is None:
        stdout = ''
    if stderr is None:
        stderr = ''

    if (not ignore_exit_code) and (rc not in check_exit_code):
        raise excp.ProcessExecutionError(exit_code=rc, stdout=stdout, \
                                         stderr=stderr, cmd=str_cmd)
    else:
        # Log it anyway
        if rc not in check_exit_code:
            LOG.debug("A failure may of just happened when running command %r [%s] (%s, %s)", \
                str_cmd, rc, stdout.strip(), stderr.strip())
        # Log for debugging figuring stuff out
        LOG.debug("Received stdout: %s" % (stdout.strip()))
        LOG.debug("Received stderr: %s" % (stderr.strip()))
        return (stdout, stderr)


def abspth(path):
    if not path:
        path = ROOT_PATH
    if path == "~":
        path = gethomedir()
    return os.path.abspath(path)


def isuseable(path, options=os.W_OK | os.R_OK | os.X_OK):
    return os.access(path, options)


def shellquote(text):
    # TODO since there doesn't seem to be a standard lib that actually works use this way...
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
        text = SHELL_WRAPPER % (text)
    return text


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


def _get_suids():
    uid = env.get_key(SUDO_UID)
    if uid is not None:
        uid = int(uid)
    gid = env.get_key(SUDO_GID)
    if gid is not None:
        gid = int(gid)
    return (uid, gid)


def chown_r(path, uid, gid, run_as_root=True):
    with Rooted(run_as_root):
        if isdir(path):
            LOG.audit("Changing ownership of %r to %s:%s" % (path, uid, gid))
            for root, dirs, files in os.walk(path):
                os.chown(root, uid, gid)
                LOG.audit("Changing ownership of %r to %s:%s" % (root, uid, gid))
                for d in dirs:
                    dir_pth = joinpths(root, d)
                    os.chown(dir_pth, uid, gid)
                    LOG.audit("Changing ownership of %r to %s:%s" % (dir_pth, uid, gid))
                for f in files:
                    fn_pth = joinpths(root, f)
                    os.chown(fn_pth, uid, gid)
                    LOG.audit("Changing ownership of %r to %s:%s" % (fn_pth, uid, gid))


def _explode_path(path):
    parts = list()
    path = abspth(path)
    while path != ROOT_PATH and path:
        (path, name) = os.path.split(path)
        parts.append(name)
    parts.reverse()
    return parts


def _explode_form_path(path):
    ret_paths = list()
    ret_paths.append(ROOT_PATH)
    ex_path = _explode_path(path)
    for i in range(len(ex_path)):
        to_make = [ROOT_PATH] + ex_path[0:i] + [ex_path[i]]
        ret_paths.append(joinpths(*to_make))
    return ret_paths


def explode_path(path):
    return _explode_form_path(path)


def in_terminal(check_both=False):
    if check_both:
        return sys.stdout.isatty() and sys.stderr.isatty()
    else:
        return sys.stdout.isatty()


def remove_parents(child_path, paths):
    if not paths:
        return list()
    cleaned_paths = [abspth(p) for p in paths]
    cleaned_child_path = abspth(child_path)
    LOG.audit("Removing parents of %r from input [%s]" % (cleaned_child_path, ",".join(cleaned_paths)))
    to_check_paths = [_explode_path(p) for p in cleaned_paths]
    check_path = _explode_path(cleaned_child_path)
    new_paths = list()
    for p in to_check_paths:
        if _array_begins_with(p, check_path):
            pass
        else:
            new_paths.append(p)
    ret_paths = list()
    for p in new_paths:
        ret_paths.append(abspth(os.sep + os.sep.join(p)))
    LOG.debug("Removal resulted in [%s]", ",".join(ret_paths))
    return ret_paths


def _array_begins_with(haystack, needle):
    if len(haystack) > len(needle):
        return False
    for i in range(len(haystack)):
        if haystack[i] != needle[i]:
            return False
    return True


def mkdirslist(path):
    LOG.debug("Determining potential paths to create for target path %r" % (path))
    dirs_possible = _explode_form_path(path)
    dirs_made = list()
    for check_path in dirs_possible:
        if not isdir(check_path):
            mkdir(check_path, False)
            dirs_made.append(check_path)
    return dirs_made


def append_file(fn, text, flush=True, quiet=False):
    if not quiet:
        LOG.audit("Appending to file %r (%d bytes) (flush=%s)", fn, len(text), BOOL2STR.get(flush))
        LOG.audit(">> %s" % (text))
    if not DRYRUN_MODE:
        with open(fn, "a") as f:
            f.write(text)
            if flush:
                f.flush()
    return fn


def write_file(fn, text, flush=True, quiet=False):
    if not quiet:
        LOG.audit("Writing to file %r (%d bytes) (flush=%s)", fn, len(text), BOOL2STR.get(flush))
        LOG.audit("> %s" % (text))
    if not DRYRUN_MODE:
        with open(fn, "w") as f:
            f.write(text)
            if flush:
                f.flush()
    return fn


def touch_file(fn, die_if_there=True, quiet=False, file_size=0):
    if not isfile(fn):
        if not quiet:
            LOG.audit("Touching and truncating file %r (truncate size=%s)", fn, file_size)
        if not DRYRUN_MODE:
            with open(fn, "w") as f:
                f.truncate(file_size)
    else:
        if die_if_there:
            msg = "Can not touch & truncate file %r since it already exists" % (fn)
            raise excp.FileException(msg)
    return fn


def load_file(fn, quiet=False):
    if not quiet:
        LOG.audit("Loading data from file %r", fn)
    data = ""
    if not DRYRUN_MODE:
        with open(fn, "r") as f:
            data = f.read()
    if not quiet:
        LOG.audit("Loaded (%d) bytes from file %r", len(data), fn)
    return data


def mkdir(path, recurse=True):
    if not isdir(path):
        if recurse:
            LOG.audit("Recursively creating directory %r" % (path))
            if not DRYRUN_MODE:
                os.makedirs(path)
        else:
            LOG.audit("Creating directory %r" % (path))
            if not DRYRUN_MODE:
                os.mkdir(path)


def deldir(path, run_as_root=False):
    with Rooted(run_as_root):
        if isdir(path):
            LOG.audit("Recursively deleting directory tree starting at %r" % (path))
            if not DRYRUN_MODE:
                shutil.rmtree(path)


def rmdir(path, quiet=True, run_as_root=False):
    if not isdir(path):
        return
    try:
        with Rooted(run_as_root):
            LOG.audit("Deleting directory %r with the cavet that we will fail if it's not empty." % (path))
            if not DRYRUN_MODE:
                os.rmdir(path)
            LOG.audit("Deleted directory %r" % (path))
    except OSError:
        if not quiet:
            raise
        else:
            pass


def symlink(source, link, force=True, run_as_root=True):
    with Rooted(run_as_root):
        LOG.audit("Creating symlink from %r => %r" % (link, source))
        path = dirname(link)
        needed_pths = mkdirslist(path)
        if not DRYRUN_MODE:
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
    (uid, _) = _get_suids()
    if uid is None:
        return getpass.getuser()
    return pwd.getpwuid(uid).pw_name


def getuid(username):
    return pwd.getpwnam(username).pw_uid


def gethomedir():
    return os.path.expanduser("~")


def getgid(groupname):
    return grp.getgrnam(groupname).gr_gid


def getgroupname():
    (_, gid) = _get_suids()
    if gid is None:
        return os.getgid()
    else:
        return grp.getgrgid(gid).gr_name


def create_loopback_file(fname, size, bsize=1024, fs_type='ext3', run_as_root=False):
    dd_cmd = ['dd', 'if=/dev/zero', 'of=%s' % fname, 'bs=%d' % bsize,
              'count=0', 'seek=%d' % size]
    mkfs_cmd = ['mkfs.%s' % fs_type, '-f', '-i', 'size=%d' % bsize, fname]

    # Make sure folder exists
    files = mkdirslist(dirname(fname))

    # Create file
    touch_file(fname)

    # Fill with zeroes
    execute(*dd_cmd, run_as_root=run_as_root)

    # Create fs on the file
    execute(*mkfs_cmd, run_as_root=run_as_root)

    return files


def mount_loopback_file(fname, device_name, fs_type='ext3'):
    mount_cmd = ['mount', '-t', fs_type, '-o',
                 'loop,noatime,nodiratime,nobarrier,logbufs=8', fname,
                 device_name]

    files = mkdirslist(device_name)

    execute(*mount_cmd, run_as_root=True)

    return files


def umount(dev_name, ignore_errors=True):
    try:
        execute('umount', dev_name, run_as_root=True)
    except excp.ProcessExecutionError:
        if not ignore_errors:
            raise
        else:
            pass


def unlink(path, ignore_errors=True, run_as_root=False):
    LOG.audit("Unlinking (removing) %r" % (path))
    if not DRYRUN_MODE:
        try:
            with Rooted(run_as_root):
                os.unlink(path)
        except OSError:
            if not ignore_errors:
                raise
            else:
                pass


def move(src, dst):
    LOG.audit("Moving: %r => %r" % (src, dst))
    if not DRYRUN_MODE:
        shutil.move(src, dst)
    return dst


def chmod(fname, mode):
    LOG.audit("Applying chmod: %r to %o" % (fname, mode))
    if not DRYRUN_MODE:
        os.chmod(fname, mode)
    return fname


def replace_in(fn, search, replace, run_as_root=False):
    with Rooted(run_as_root):
        contents = load_file(fn)

        def replacer(match):
            return replace

        (contents, num_changed) = search.subn(replacer, contents)
        if num_changed:
            write_file(fn, contents)


def copy_replace_file(fsrc, fdst, linemap):
    files = mkdirslist(dirname(fdst))
    LOG.audit("Copying and replacing file: %r => %r" % (fsrc, fdst))
    if not DRYRUN_MODE:
        with open(fdst, 'w') as fh:
            for line in fileinput.input(fsrc):
                for (k, v) in linemap.items():
                    line = line.replace(k, v)
                fh.write(line)
    return files


def got_root():
    return os.geteuid() == ROOT_USER_UID


def root_mode(quiet=True):
    root_uid = getuid(ROOT_USER)
    root_gid = getgid(ROOT_USER)
    if root_uid is None or root_gid is None:
        msg = "Cannot escalate permissions to (user=%s) - does that user exist??" % (ROOT_USER)
        if quiet:
            LOG.warn(msg)
        else:
            raise excp.StackException(msg)
    else:
        try:
            LOG.debug("Escalating permissions to (user=%s, group=%s)" % (root_uid, root_gid))
            os.setreuid(0, root_uid)
            os.setregid(0, root_gid)
        except OSError:
            if quiet:
                LOG.warn("Cannot escalate permissions to (user=%s, group=%s)" % (root_uid, root_gid))
            else:
                raise


def user_mode(quiet=True):
    (sudo_uid, sudo_gid) = _get_suids()
    if sudo_uid is not None and sudo_gid is not None:
        try:
            LOG.debug("Dropping permissions to (user=%s, group=%s)" % (sudo_uid, sudo_gid))
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
            raise excp.StackException(msg)


def is_executable(fn):
    return isfile(fn) and os.access(fn, os.X_OK)


def geteuid():
    return os.geteuid()


def getegid():
    return os.getegid()


def sleep(winks):
    if DRYRUN_MODE:
        LOG.audit("Not really sleeping for: %s seconds" % (winks))
    else:
        time.sleep(winks)
