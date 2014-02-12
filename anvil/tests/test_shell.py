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

import mock
import subprocess

from anvil import exceptions as exc
from anvil import shell as sh
from anvil import test


class TestShell(test.MockTestCase):

    def setUp(self):
        super(TestShell, self).setUp()
        self.cmd = ['test', 'command']
        self.result = ('stdout', 'stderr')

        # patch subprocess.Popen
        self.popen_mock, self.popen_inst_mock = self._patch_class(
            sh.subprocess, 'Popen')
        self.popen_inst_mock.returncode = 0
        self.popen_inst_mock.communicate.return_value = self.result

    def tearDown(self):
        sh.IS_DRYRUN = False
        super(TestShell, self).tearDown()

    def test_execute_dry_run(self):
        sh.IS_DRYRUN = True
        self.assertEqual(sh.execute(self.cmd), ('', ''))
        self.assertEqual(self.master_mock.mock_calls, [])

    def test_execute_with_result(self):
        self.assertEqual(sh.execute(self.cmd), self.result)
        self.assertEqual(self.master_mock.mock_calls, [
            mock.call.Popen(self.cmd,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            close_fds=True,
                            shell=False,
                            cwd=None,
                            env=None),
            mock.call.popen.communicate(None)
        ])

    def test_execute_with_input(self):
        self.assertEqual(sh.execute(self.cmd, process_input='input'),
                         self.result)
        self.assertEqual(self.master_mock.mock_calls, [
            mock.call.Popen(self.cmd,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            close_fds=True,
                            shell=False,
                            cwd=None,
                            env=None),
            mock.call.popen.communicate('input')
        ])

    @mock.patch.object(sh.env, 'get')
    def test_execute_all_params(self, mocked_env_get):
        mocked_env_get.return_value = {'a': 'a'}
        env = {'b': 'b'}
        sh.execute(self.cmd, cwd='cwd', shell=True, env_overrides=env,
                   stdout_fh='stdout_fh', stderr_fh='stderr_fh')
        env.update({'a': 'a'})
        self.assertEqual(self.master_mock.mock_calls, [
            mock.call.Popen(' '.join(self.cmd),
                            stdin=subprocess.PIPE,
                            stdout='stdout_fh',
                            stderr='stderr_fh',
                            close_fds=True,
                            shell=True,
                            cwd='cwd',
                            env=env),
            mock.call.popen.communicate(None)
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
                                "Stdout: stdout.*\nStderr: stderr",
                                sh.execute, self.cmd)

    def test_execute_bad_return_code_with_tail(self):
        stdout = '1\n2\n3\n4\n5\n6\n7\n8\n'
        self.popen_inst_mock.returncode = 1
        self.popen_inst_mock.communicate.return_value = (stdout, '')
        self.assertRaisesRegexp(
            exc.ProcessExecutionError,
            "Stdout: <redirected to debug log>\n...\n4\n5\n6\n7\n8\n",
            sh.execute, self.cmd)

    @mock.patch.object(sh, 'mkdirslist')
    def test_execute_save_output(self, mocked_mkdirslist):
        self.popen_inst_mock.returncode = 1
        file_name = 'output.txt'
        m = mock.mock_open()
        with mock.patch.object(sh, 'open', m, create=True):
            m.return_value.name = file_name
            self.assertRaisesRegexp(
                exc.ProcessExecutionError,
                "Stdout: <redirected to %s>\n"
                "Stderr: <redirected to %s>" % (file_name, file_name),
                sh.execute_save_output, self.cmd, file_name)
