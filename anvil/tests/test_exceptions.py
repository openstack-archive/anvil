# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2013 Yahoo! Inc. All Rights Reserved.
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

from anvil import exceptions as exc
from anvil import test


class TestProcessExecutionError(test.TestCase):

    def assertExceptionMessage(self, err, cmd, stdout='', stderr='',
                               exit_code='-', description=None):
        if description is None:
            description = 'Unexpected error while running command.'
        message = ('%s\nCommand: %s\nExit code: %s\nStdout: %s\nStderr: %s' %
                   (description, cmd, exit_code, stdout, stderr))
        self.assertEqual(err.message, message)

    def setUp(self):
        super(TestProcessExecutionError, self).setUp()
        self.cmd = 'test-command'
        self.stdout = 'test-stdout'
        self.stderr = 'test-stderr'

    def test_default(self):
        err = exc.ProcessExecutionError(self.cmd, {})
        self.assertExceptionMessage(err, cmd=self.cmd)

    def test_stdout(self):
        err = exc.ProcessExecutionError(self.cmd, {}, stdout=self.stdout)
        self.assertExceptionMessage(err, cmd=self.cmd, stdout=self.stdout)
        self.assertEqual(self.stdout, err.stdout())

    def test_stdout_empty(self):
        err = exc.ProcessExecutionError(self.cmd, {}, stdout='')
        self.assertExceptionMessage(err, cmd=self.cmd, stdout='')
        self.assertEqual('', err.stdout())

    def test_stdout_none(self):
        err = exc.ProcessExecutionError(self.cmd, {}, stdout=None)
        self.assertExceptionMessage(err, cmd=self.cmd, stdout=None)

    def test_stderr(self):
        err = exc.ProcessExecutionError(self.cmd, {}, stderr=self.stderr)
        self.assertExceptionMessage(err, cmd=self.cmd, stderr=self.stderr)
        self.assertEqual(self.stderr, err.stderr())

    def test_stderr_none(self):
        err = exc.ProcessExecutionError(self.cmd, {}, stderr=None)
        self.assertExceptionMessage(err, cmd=self.cmd, stderr=None)

    def test_exit_code_int(self):
        err = exc.ProcessExecutionError(self.cmd, {}, exit_code=0)
        self.assertExceptionMessage(err, self.cmd, exit_code=0)

    def test_exit_code_long(self):
        err = exc.ProcessExecutionError(self.cmd, {}, exit_code=0L)
        self.assertExceptionMessage(err, self.cmd, exit_code=0L)

    def test_exit_code_not_valid(self):
        err = exc.ProcessExecutionError(self.cmd, {}, exit_code='code')
        self.assertExceptionMessage(err, self.cmd, exit_code='-')
        err = exc.ProcessExecutionError(self.cmd, {}, exit_code=0.0)
        self.assertExceptionMessage(err, self.cmd, exit_code='-')

    def test_description(self):
        description = 'custom description'
        err = exc.ProcessExecutionError(self.cmd, {}, description=description)
        self.assertExceptionMessage(err, self.cmd, description=description)


class TestReraise(test.TestCase):
    def test_reraise_exception(self):
        buff = []

        def failure():
            raise IOError("Broken")

        def activate():
            try:
                failure()
            except Exception:
                with exc.reraise():
                    buff.append(1)

        self.assertRaises(IOError, activate)
        self.assertEqual([1], buff)

    def test_override_reraise_exception(self):

        def failure():
            raise IOError("Broken")

        def activate():
            try:
                failure()
            except Exception:
                with exc.reraise():
                    raise RuntimeError("Really broken")

        self.assertRaises(RuntimeError, activate)


class TestYamlException(test.TestCase):

    def test_yaml_exception(self):
        self.assertTrue(issubclass(exc.YamlException,
                                   exc.ConfigException))

    def test_yaml_option_not_found_exception(self):
        self.assertTrue(issubclass(exc.YamlOptionNotFoundException,
                                   exc.YamlException))

        exc_str = str(exc.YamlOptionNotFoundException(
            'conf-sample', 'opt-sample', 'ref-conf', 'ref-opt'
        ))
        self.assertTrue("`conf-sample`" in exc_str)
        self.assertTrue("`ref-opt`" in exc_str)
        self.assertTrue("opt-sample" in exc_str)
        self.assertTrue("ref-conf:ref-opt" in exc_str)

    def test_yaml_config_not_found_exception(self):
        self.assertTrue(issubclass(exc.YamlConfigNotFoundException,
                                   exc.YamlException))

        exc_str = str(exc.YamlConfigNotFoundException("no/such//path/to/yaml"))
        self.assertTrue("no/such//path/to/yaml" in exc_str)

    def test_yaml_loop_exception(self):
        self.assertTrue(issubclass(exc.YamlLoopException, exc.YamlException))

        exc_str = str(exc.YamlLoopException('conf-sample', 'opt-sample',
                                            [('s1', 'r1'), ('s2', 'r2')]))
        self.assertTrue("`conf-sample`" in exc_str)
        self.assertTrue("`opt-sample`" in exc_str)
        self.assertTrue("loop found" in exc_str)
        self.assertTrue("`s1`=>`r1`" in exc_str)
        self.assertTrue("`s2`=>`r2`" in exc_str)
