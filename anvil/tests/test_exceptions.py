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

import unittest

from anvil import exceptions


class TestYamlException(unittest.TestCase):

    def test_YamlException(self):
        self.assertTrue(issubclass(exceptions.YamlException,
                                   exceptions.ConfigException))

    def test_YamlOptionNotFoundException(self):
        self.assertTrue(issubclass(exceptions.YamlOptionNotFoundException,
                                   exceptions.YamlException))

        exc = str(exceptions.YamlOptionNotFoundException(
            'conf-sample', 'opt-sample', 'ref-conf', 'ref-opt'
        ))
        self.assertTrue("`conf-sample`" in exc)
        self.assertTrue("`ref-opt`" in exc)
        self.assertTrue("opt-sample" in exc)
        self.assertTrue("ref-conf:ref-opt" in exc)

    def test_YamlConfigNotFoundException(self):
        self.assertTrue(issubclass(exceptions.YamlConfigNotFoundException,
                                   exceptions.YamlException))

        exc = str(exceptions.YamlConfigNotFoundException(
            "no/such//path/to/yaml"
        ))
        self.assertTrue("no/such//path/to/yaml" in exc)

    def test_YamlLoopException(self):
        self.assertTrue(issubclass(exceptions.YamlLoopException,
                                   exceptions.YamlException))

        exc = str(exceptions.YamlLoopException('conf-sample', 'opt-sample',
                                               [('s1', 'r1'), ('s2', 'r2')]))

        self.assertTrue("`conf-sample`" in exc)
        self.assertTrue("`opt-sample`" in exc)
        self.assertTrue("loop found" in exc)
        self.assertTrue("`s1`=>`r1`" in exc)
        self.assertTrue("`s2`=>`r2`" in exc)
