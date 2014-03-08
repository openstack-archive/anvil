# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2014 Yahoo! Inc. All Rights Reserved.
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
import tempfile

import mock

from anvil import exceptions as exc
from anvil import shell as sh
from anvil import test


class TestShell(test.MockTestCase):

    def setUp(self):
        super(TestShell, self).setUp()
        self.cmd = ['test', 'command']
        self.str_cmd = ' '.join(self.cmd)
        self.result = ('stdout', 'stderr')

        # patch subprocess.Popen
        self.popen_mock, self.popen_inst_mock = self._patch_class(
            sh.subprocess, 'Popen')
        self.popen_inst_mock.returncode = 0
        self.popen_inst_mock.communicate.return_value = self.result

    def test_reverse_reader(self):
        with tempfile.NamedTemporaryFile() as fh:
            fh.write("test\n")
            fh.write("test2\n")
            fh.flush()

            with sh.ReverseFile(fh.name) as rh:
                lines = list(rh.readlines())
            self.assertEqual(['', 'test2', 'test'], lines)

            with sh.ReverseFile(fh.name) as rh:
                lines = list(rh.readlines(include_last_newline=False))
            self.assertEqual(['test2', 'test'], lines)

            with sh.ReverseFile(fh.name) as rh:
                lines = list(rh.readlines(include_newline=True))
            self.assertEqual(['\n', '\ntest2', 'test'], lines)

    def test_reverse_read_closed(self):
        def read_all(rh):
            return list(rh.readlines())

        with tempfile.NamedTemporaryFile() as fh:
            fh.write("test\n")
            fh.write("test2\n")
            rh = sh.ReverseFile(fh.name)
            rh.close()
            self.assertRaises(ValueError, read_all, rh)

    def test_execute_dry_run(self):
        sh.IS_DRYRUN = True
        self.assertEqual(sh.execute(self.cmd), ('', ''))
        self.assertEqual(self.master_mock.mock_calls, [])
        sh.IS_DRYRUN = False

    def test_execute_default_params(self):
        result = sh.execute(self.cmd)
        master_mock_calls = [
            mock.call.Popen(self.cmd,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            close_fds=True,
                            shell=False,
                            cwd=None,
                            env=None),
            mock.call.popen.communicate(None)
        ]

        self.assertEqual(self.master_mock.mock_calls, master_mock_calls)
        self.assertEqual(result, self.result)

    @mock.patch.object(sh.env, 'get')
    def test_execute_custom_params(self, mocked_env_get):
        mocked_env_get.return_value = {'a': 'a'}
        env = {'b': 'b'}
        sh.execute(self.cmd,
                   process_input='input',
                   cwd='cwd',
                   shell=True,
                   env_overrides=env,
                   stdout_fh='stdout_fh',
                   stderr_fh='stderr_fh')
        env.update({'a': 'a'})

        self.assertEqual(self.master_mock.mock_calls, [
            mock.call.Popen(self.str_cmd,
                            stdin=subprocess.PIPE,
                            stdout='stdout_fh',
                            stderr='stderr_fh',
                            close_fds=True,
                            shell=True,
                            cwd='cwd',
                            env=env),
            mock.call.popen.communicate('input')
        ])

    def test_execute_with_result_none(self):
        self.popen_inst_mock.communicate.return_value = (None, None)
        self.assertEqual(sh.execute(self.cmd), ('', ''))

    def test_execute_popen_raises(self):
        self.popen_mock.side_effect = OSError('Woot!')
        self.assertRaises(exc.ProcessExecutionError, sh.execute, self.cmd)

    def test_execute_communicate_raises(self):
        self.popen_inst_mock.communicate.side_effect = OSError('Woot!')
        self.assertRaises(exc.ProcessExecutionError, sh.execute, self.cmd)

    def test_execute_bad_return_code_no_check(self):
        self.popen_inst_mock.returncode = 1
        self.assertEqual(sh.execute(self.cmd, check_exit_code=False),
                         self.result)

    def test_execute_bad_return_code_with_check(self):
        self.popen_inst_mock.returncode = 1
        self.assertRaisesRegexp(exc.ProcessExecutionError,
                                "Unexpected error while running command.\n"
                                "Command: %s\n"
                                "Exit code: 1\n"
                                "Stdout: stdout\n"
                                "Stderr: stderr" % self.str_cmd,
                                sh.execute, self.cmd)

    def test_execute_bad_return_code_with_tail(self):
        self.popen_inst_mock.returncode = 1
        self.popen_inst_mock.communicate.return_value = (
            '0\n1\n2\n3\n4\n5\n6\n7\n8\n', '')
        stdout = ('2\n3\n4\n5\n6\n7\n8\n')
        expected = (
            "Unexpected error while running command.\n"
            "Command: %s\n"
            "Exit code: 1\n"
            "Stdout: %s \(see debug log for more details...\)\n"
            "Stderr: " % (self.str_cmd, stdout)
        )
        self.assertRaisesRegexp(exc.ProcessExecutionError,
                                expected, sh.execute, self.cmd)

    @mock.patch.object(sh, 'mkdirslist')
    def test_execute_save_output(self, mocked_mkdirslist):
        self.popen_inst_mock.returncode = 1
        file_name = 'output.txt'
        with mock.patch.object(sh, 'open', mock.mock_open(),
                               create=True) as fh_mock:
            with mock.patch.object(sh, 'getsize') as size_mock:
                size_mock.return_value = 0
                fh_mock.return_value.name = file_name
                self.assertRaisesRegexp(
                    exc.ProcessExecutionError,
                    "Unexpected error while running command.\n"
                    "Command: %s\n"
                    "Exit code: 1\n"
                    "Stdout: <redirected to %s>\n"
                    "Stderr: <redirected to %s>" % (self.str_cmd, file_name,
                                                    file_name),
                    sh.execute_save_output, self.cmd, file_name
                )
