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

from anvil import exceptions as exc
from anvil import shell as sh
from anvil import test


class TestShell(test.MockTestCase):

    def setUp(self):
        super(TestShell, self).setUp()
        self.cmd = 'test-command'

        # patch classes
        self.popen_mock, self.popen_inst_mock = self._patch_class(
            sh.subprocess, 'Popen', autospec=False)

    def tearDown(self):
        sh.IS_DRYRUN = False
        super(TestShell, self).tearDown()

    def test_execute_dry_run(self):
        sh.IS_DRYRUN = True
        stdout, stderr = sh.execute(self.cmd)
        self.assertEqual((stdout, stderr), ('', ''))

    def test_execute_popen_raises(self):
        self.popen_mock.side_effect = OSError('Woot!')
        self.assertRaises(exc.ProcessExecutionError, sh.execute, self.cmd)

    def test_execute_communicate_raises(self):
        self.popen_inst_mock.communicate.side_effect = OSError('Woot!')
        self.assertRaises(exc.ProcessExecutionError, sh.execute, self.cmd)
