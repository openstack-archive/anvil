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

from anvil import downloader
from anvil import exceptions
from anvil import test


class TestGitDownloader(test.TestCase):

    def setUp(self):
        super(TestGitDownloader, self).setUp()
        self._uri = 'https://github.com/stackforge/anvil.git'
        self._dst = '/root/anvil'
        self._sha1 = '0a4d55a8d778e5022fab701977c5d840bbc486d0'
        self._tag = '1.0.6'

    def test_constructor_basic(self):
        d = downloader.GitDownloader(self._uri, self._dst)
        self.assertEqual(d._uri, self._uri)
        self.assertEqual(d._dst, self._dst)
        self.assertEqual(d._branch, 'master')
        self.assertIsNone(d._tag)
        self.assertIsNone(d._sha1)

    def test_constructor_branch(self):
        branch = 'stable/havana'
        d = downloader.GitDownloader(self._uri, self._dst, branch=branch)
        self.assertEqual(d._branch, branch)
        self.assertIsNone(d._tag)
        self.assertIsNone(d._sha1)

    def test_constructor_string_tag(self):
        d = downloader.GitDownloader(self._uri, self._dst, tag=self._tag)
        self.assertEqual(d._tag, self._tag)
        self.assertIsNone(d._sha1)

    def test_constructor_float_tag(self):
        tag = 2013.2
        d = downloader.GitDownloader(self._uri, self._dst, tag=tag)
        self.assertEqual(d._tag, str(tag))
        self.assertIsNone(d._sha1)

    def test_constructor_sha1(self):
        d = downloader.GitDownloader(self._uri, self._dst, sha1=self._sha1)
        self.assertIsNone(d._tag)
        self.assertEqual(d._sha1, self._sha1)

    def test_constructor_raises_exception(self):
        kwargs = {"tag": self._tag, 'sha1': self._sha1}
        self.assertRaises(exceptions.ConfigException,
                          downloader.GitDownloader,
                          self._uri, self._dst, **kwargs)
