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


class StackException(Exception):
    pass


class InstallException(StackException):
    pass


class PackageException(StackException):
    pass


class BadRegexException(StackException):
    pass


class DependencyException(StackException):
    pass


class BadParamException(StackException):
    pass


class NoTraceException(StackException):
    pass


class NoReplacementException(StackException):
    pass


class StartException(StackException):
    pass


class NoIpException(StackException):
    pass


class StopException(StackException):
    pass


class RestartException(StackException):
    pass


class StatusException(StackException):
    pass


class FileException(StackException):
    pass


class ConfigException(StackException):
    pass


class ProcessExecutionError(IOError):
    def __init__(self, stdout=None, stderr=None, exit_code=None, cmd=None,
                 description=None):
        self.exit_code = exit_code
        self.stderr = stderr
        self.stdout = stdout
        self.cmd = cmd
        self.description = description
        if description is None:
            description = ('Unexpected error while running command.')
        if exit_code is None:
            exit_code = '-'
        message = ('%(description)s\nCommand: %(cmd)s\n'
                    'Exit code: %(exit_code)s\nStdout: %(stdout)r\n'
                    'Stderr: %(stderr)r' % locals())
        IOError.__init__(self, message)
