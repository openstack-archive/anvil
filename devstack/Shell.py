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

import subprocess
import shlex
import getpass
import sys
import os.path
import os
import shutil
import json

import Exceptions
from Exceptions import ProcessExecutionError, FileException
import Logger

ROOT_HELPER = ["sudo"]
MKPW_CMD = ["openssl", 'rand', '-hex']

LOG = Logger.getLogger("install.shell")


def execute(*cmd, **kwargs):
    process_input = kwargs.pop('process_input', None)
    check_exit_code = kwargs.pop('check_exit_code', [0])
    cwd = kwargs.pop('cwd', None)
    env_overrides = kwargs.pop('env_overrides', None)
    ignore_exit_code = False

    if(isinstance(check_exit_code, bool)):
        ignore_exit_code = not check_exit_code
        check_exit_code = [0]
    elif(isinstance(check_exit_code, int)):
        check_exit_code = [check_exit_code]

    run_as_root = kwargs.pop('run_as_root', False)
    shell = kwargs.pop('shell', False)
    if run_as_root:
        cmd = ROOT_HELPER + list(cmd)

    cmd = map(str, cmd)
    if(shell):
        cmd = " ".join(cmd)
        LOG.debug('Running shell cmd: [%s]' % (cmd))
    else:
        LOG.debug('Running cmd: [%s]' % (' '.join(cmd)))

    if(process_input != None):
        LOG.debug('With stdin: %s' % (process_input))

    stdin_fh = subprocess.PIPE
    stdout_fh = subprocess.PIPE
    stderr_fh = subprocess.PIPE
    close_file_descriptors = True

    if('stdout_fh' in kwargs.keys()):
        stdout_fh = kwargs.get('stdout_fh')
        LOG.debug("Redirecting stdout to file handle %s" % (stdout_fh))

    if('stdin_fh' in kwargs.keys()):
        stdin_fh = kwargs.get('stdin_fh')
        LOG.debug("Redirecting stdin to file handle %s" % (stdin_fh))

    if('stderr_fh' in kwargs.keys()):
        stderr_fh = kwargs.get('stderr_fh')
        LOG.debug("Redirecting stderr to file handle %s" % (stderr_fh))

    process_env = os.environ or {}
    if(env_overrides and len(env_overrides)):
        LOG.debug("With additional environment overrides: %s" % (env_overrides))
        for (k, v) in env_overrides.items():
            process_env[k] = str(v)

    obj = subprocess.Popen(cmd,
            stdin=stdin_fh,
            stdout=stdout_fh,
            stderr=stderr_fh,
            close_fds=close_file_descriptors,
            cwd=cwd,
            shell=shell,
            env=process_env)

    result = None
    if(process_input != None):
        result = obj.communicate(str(process_input))
    else:
        result = obj.communicate()

    obj.stdin.close()
    _returncode = obj.returncode
    LOG.debug('Cmd result had return code %s' % _returncode)

    if((not ignore_exit_code) and (_returncode not in check_exit_code)):
        (stdout, stderr) = result
        ecmd = cmd
        if(not shell):
            ecmd = ' '.join(cmd)
        raise ProcessExecutionError(
                exit_code=_returncode,
                stdout=stdout,
                stderr=stderr,
                cmd=ecmd)
    else:
        return result


def isfile(fn):
    return os.path.isfile(fn)


def joinpths(*pths):
    return os.path.join(*pths)


def password(prompt=None, genlen=8):
    if(prompt):
        rd = getpass.getpass(prompt)
    else:
        rd = getpass.getpass()
    if(len(rd) == 0):
        LOG.debug("Generating you a password of length %s" % (genlen))
        cmd = MKPW_CMD + [genlen]
        (stdout, stderr) = execute(*cmd)
        return stdout.strip()
    else:
        return rd


def mkdirslist(pth):
    dirsmade = list()
    if(os.path.isdir(pth)):
        #already there...
        return dirsmade
    dirspossible = set()
    dirspossible.add(pth)
    while(True):
        splitup = os.path.split(pth)
        pth = splitup[0]
        base = splitup[1]
        dirspossible.add(pth)
        if(len(base) == 0):
            break
    dirstobe = list(dirspossible)
    dirstobe.sort()
    for pth in dirstobe:
        if(not os.path.isdir(pth)):
            os.mkdir(pth)
            dirsmade.append(pth)
    return dirsmade


def load_json(fn):
    data = load_file(fn)
    lines = data.splitlines()
    nlines = list()
    for line in lines:
        if(line.lstrip().startswith('#')):
            continue
        nlines.append(line)
    data = os.linesep.join(nlines)
    return json.loads(data)


def append_file(fn, text, flush=True):
    with open(fn, "a") as f:
        f.write(text)
        if(flush):
            f.flush()


def write_file(fn, text, flush=True):
    with open(fn, "w") as f:
        f.write(text)
        if(flush):
            f.flush()


def touch_file(fn, diethere=True):
    if(not os.path.exists(fn)):
        with open(fn, "w") as f:
            f.truncate(0)
    else:
        if(diethere):
            msg = "Can not touch file %s since it already exists" % (fn)
            raise FileException(msg)


def load_file(fn):
    data = ""
    with open(fn, "r") as f:
        data = f.read()
    return data


def mkdir(pth, recurse=True):
    if(not os.path.isdir(pth)):
        if(recurse):
            os.makedirs(pth)
        else:
            os.mkdir(pth)


def deldir(pth, force=True):
    if(os.path.isdir(pth)):
        if(force):
            shutil.rmtree(pth)
        else:
            os.removedirs(pth)


def prompt(prompt):
    rd = raw_input(prompt)
    return rd


def unlink(pth, ignore=True):
    try:
        os.unlink(pth)
    except OSError as (errono, emsg):
        if(not ignore):
            raise
