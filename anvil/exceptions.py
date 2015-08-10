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


class AnvilException(Exception):
    pass


class PermException(AnvilException):
    pass


class OptionException(AnvilException):
    pass


class DownloadException(AnvilException):
    pass


class NoTraceException(AnvilException):
    pass


class PackageException(AnvilException):
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

    # Truncate stdout & stderr content to this many lines when creating a
    # process execution error (the full stdout/stderr can still be accessed).
    _TRUNCATED_OUTPUT_LINES = 7

    def __init__(self, cmd, exec_kwargs=None,
                 stdout='', stderr='', exit_code=None, description=None,
                 where_output=None):
        if not isinstance(exit_code, (long, int)):
            exit_code = '-'
        if not description:
            description = 'Unexpected error while running command.'
        if not exec_kwargs:
            exec_kwargs = {}
        self._stdout = self._format(exec_kwargs.get('stdout'), stdout)
        self._stderr = self._format(exec_kwargs.get('stderr'), stderr)
        message = self.MESSAGE_TPL % {
            'exit_code': exit_code,
            'command': cmd,
            'description': description,
            'stdout': self._truncate_lines(self._stdout, where_output),
            'stderr': self._truncate_lines(self._stderr, where_output),
        }
        IOError.__init__(self, message)

    @classmethod
    def _truncate_lines(cls, content, where_output=None):
        """Truncates a given text blob using the class defined line limit."""
        if not content:
            return content
        lines = content.splitlines(True)
        if len(lines) > cls._TRUNCATED_OUTPUT_LINES:
            content = "".join(lines[-cls._TRUNCATED_OUTPUT_LINES:])
            if where_output:
                content += " (see %s for more details...)" % (where_output)
            else:
                content += "..."
        return content

    @staticmethod
    def _format(stream, output):
        if stream != subprocess.PIPE and stream is not None:
            return "<redirected to %s>" % stream.name
        return output

    @property
    def stdout(self):
        """Access the full (non-truncated) stdout."""
        return self._stdout

    @property
    def stderr(self):
        """Access the full (non-truncated) stderr."""
        return self._stderr


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
