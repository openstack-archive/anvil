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

from testtools import testcase


class TestCase(testcase.TestCase):
    """Base test case class for all anvil tests."""


class MockTestCase(TestCase):
    """Base test case class from all anvil tests with mock."""

    def setUp(self):
        super(MockTestCase, self).setUp()
        self.master_mock = mock.MagicMock(name='master_mock')

    def _patch_class(self, module, name, autospec=True, attach_as=None):
        """Patch class, create class instance mock and attach them to
        the master mock.
        """
        if autospec:
            instance_mock = mock.MagicMock(spec=getattr(module, name))
        else:
            instance_mock = mock.MagicMock()

        patcher = mock.patch.object(module, name, autospec=autospec)
        class_mock = patcher.start()
        self.addCleanup(patcher.stop)
        class_mock.return_value = instance_mock

        if attach_as is None:
            attach_class_as = name
            attach_instance_as = name.lower()
        else:
            attach_class_as = attach_as + '_class'
            attach_instance_as = attach_as

        self.master_mock.attach_mock(class_mock, attach_class_as)
        self.master_mock.attach_mock(instance_mock, attach_instance_as)

        return class_mock, instance_mock
