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

import contextlib
import subprocess
import sys

import six

# Leave this many lines when truncating output by default
TRUNCATED_OUTPUT_LINES = 7


class AnvilException(Exception):
    pass


class PermException(AnvilException):
    pass


class OptionException(AnvilException):
    pass


class DownloadException(AnvilException):
    pass


class InstallException(AnvilException):
    pass


class BadParamException(AnvilException):
    pass


class NoTraceException(AnvilException):
    pass


class NoReplacementException(AnvilException):
    pass


class StartException(AnvilException):
    pass


class PackageException(AnvilException):
    pass


class StopException(AnvilException):
    pass


class RestartException(AnvilException):
    pass


class StatusException(AnvilException):
    pass


class PasswordException(AnvilException):
    pass


class FileException(AnvilException):
    pass


class ConfigException(AnvilException):
    pass


class DependencyException(AnvilException):
    pass


class ProcessExecutionError(IOError):
    MESSAGE_TPL = (
        '%(description)s\n'
        'Command: %(command)s\n'
        'Exit code: %(exit_code)s\n'
        'Stdout: %(stdout)s\n'
        'Stderr: %(stderr)s'
    )

    def __init__(self, cmd, exec_kwargs=None,
                 stdout='', stderr='', exit_code=None, description=None):
        if not isinstance(exit_code, (long, int)):
            exit_code = '-'
        if not description:
            description = 'Unexpected error while running command.'
        if not exec_kwargs:
            exec_kwargs = {}
        message = self.MESSAGE_TPL % {
            'exit_code': exit_code,
            'command': cmd,
            'description': description,
            'stdout': self._format(exec_kwargs.get('stdout'), stdout),
            'stderr': self._format(exec_kwargs.get('stderr'), stderr),
        }
        IOError.__init__(self, message)
        self._exec_kwargs = exec_kwargs
        self._stdout = stdout
        self._stderr = stderr

    @staticmethod
    def _format(stream, output, truncate_len=TRUNCATED_OUTPUT_LINES):
        if stream != subprocess.PIPE and stream is not None:
            return "<redirected to %s>" % stream.name
        if truncate_len < 0 or output is None:
            return output
        lines = output.splitlines(True)
        if len(lines) > truncate_len:
            output_tail = ''.join(lines[-truncate_len:])
            output = ("<truncated, look to debug log for full output>\n%s"
                      % output_tail)
        return output

    def stdout(self, truncate=True):
        if not truncate:
            truncate_len = -1
        else:
            truncate_len = TRUNCATED_OUTPUT_LINES
        return self._format(self._exec_kwargs.get('stdout'),
                            self._stdout,
                            truncate_len=truncate_len)

    def stderr(self, truncate=True):
        if not truncate:
            truncate_len = -1
        else:
            truncate_len = TRUNCATED_OUTPUT_LINES
        return self._format(self._exec_kwargs.get('stderr'),
                            self._stderr,
                            truncate_len=truncate_len)


class YamlException(ConfigException):
    pass


class YamlOptionNotFoundException(YamlException):
    """Raised by YamlRefLoader if reference option not found."""
    def __init__(self, conf, opt, ref_conf, ref_opt):
        msg = "In `{0}`=>`{1}: '$({2}:{3})'` " \
              "reference option `{3}` not found." \
              .format(conf, opt, ref_conf, ref_opt)
        super(YamlOptionNotFoundException, self).__init__(msg)


class YamlConfigNotFoundException(YamlException):
    """Raised by YamlRefLoader if config source not found."""
    def __init__(self, path):
        msg = "Could not find (open) yaml source {0}.".format(path)
        super(YamlConfigNotFoundException, self).__init__(msg)


class YamlLoopException(YamlException):
    """Raised by YamlRefLoader if reference loop found."""
    def __init__(self, conf, opt, ref_stack):
        prettified_stack = "".join(
            "\n%s`%s`=>`%s`" % (" " * i, c, o)
            for i, (c, o) in enumerate(ref_stack))
        msg = "In `{0}`=>`{1}` reference loop found.\n" \
              "Reference stack is:{2}." \
              .format(conf, opt, prettified_stack)

        super(YamlLoopException, self).__init__(msg)


@contextlib.contextmanager
def reraise():
    ex_type, ex, ex_tb = sys.exc_info()
    try:
        yield ex
    except Exception:
        raise
    else:
        six.reraise(ex_type, ex, ex_tb)
