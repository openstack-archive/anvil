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

from anvil import downloader
from anvil import exceptions


class TestGitDownloader(unittest.TestCase):

    def setUp(self):
        self._uri = 'https://github.com/stackforge/anvil.git'
        self._dst = '/root/anvil'

    def test_constructor_basic(self):
        d = downloader.GitDownloader(self._uri, self._dst)
        self.assertEqual(d._uri, self._uri)
        self.assertEqual(d._dst, self._dst)
        self.assertEqual(d._branch, 'master')
        self.assertEqual(d._tag, None)
        self.assertEqual(d._sha1, None)

    def test_constructor_branch(self):
        branch = 'stable/havana'
        d = downloader.GitDownloader(self._uri, self._dst,
                                     branch=branch)
        self.assertEqual(d._branch, branch)
        self.assertEqual(d._tag, None)
        self.assertEqual(d._sha1, None)

    def test_constructor_tag(self):
        tag = '1.0.6'
        d = downloader.GitDownloader(self._uri, self._dst,
                                     tag=tag)
        self.assertEqual(d._branch, 'master')
        self.assertEqual(d._tag, tag)
        self.assertEqual(d._sha1, None)

    def test_constructor_float_tag(self):
        tag = 2013.2
        d = downloader.GitDownloader(self._uri, self._dst,
                                     tag=tag)
        self.assertEqual(d._branch, 'master')
        self.assertEqual(d._tag, str(tag))
        self.assertEqual(d._sha1, None)

    def test_constructor_branch_and_tag(self):
        branch = 'stable/havana'
        tag = 2013.2
        d = downloader.GitDownloader(self._uri, self._dst,
                                     branch=branch, tag=tag)
        self.assertEqual(d._branch, branch)
        self.assertEqual(d._tag, str(tag))
        self.assertEqual(d._sha1, None)

    def test_constructor_sha1(self):
        sha1 = 'abcd1234'
        d = downloader.GitDownloader(self._uri, self._dst,
                                     sha1=sha1)
        self.assertEqual(d._branch, 'master')
        self.assertEqual(d._tag, None)
        self.assertEqual(d._sha1, 'abcd1234')

    def test_constructor_raises_exception(self):
        sha1 = 'abcd1234'
        tag = 2013.2
        kwargs = {"tag": tag, "sha1": sha1}
        self.assertRaises(exceptions.ConfigException,
                            downloader.GitDownloader,
                            self._uri, self._dst, **kwargs)
