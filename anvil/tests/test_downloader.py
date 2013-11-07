import unittest

from anvil import downloader


class TestGitDownloader(unittest.TestCase):

    def setUp(self):
        self._uri = 'https://github.com/stackforge/anvil.git'
        self._dst = '/root/anvil'

    def test_constructor_basic(self):
        d = downloader.GitDownloader(self._uri, self._dst)
        self.assertEquals(d._uri, self._uri)
        self.assertEquals(d._dst, self._dst)
        self.assertEquals(d._branch, 'master')
        self.assertEquals(d._tag, None)

    def test_constructor_branch(self):
        branch = 'stable/havana'
        d = downloader.GitDownloader(self._uri, self._dst,
                                     branch=branch)
        self.assertEquals(d._branch, branch)
        self.assertEquals(d._tag, None)

    def test_constructor_tag(self):
        tag = '1.0.6'
        d = downloader.GitDownloader(self._uri, self._dst,
                                     tag=tag)
        self.assertEquals(d._branch, 'master')
        self.assertEquals(d._tag, tag)

    def test_constructor_float_tag(self):
        tag = 2013.2
        d = downloader.GitDownloader(self._uri, self._dst,
                                     tag=tag)
        self.assertEquals(d._branch, 'master')
        self.assertEquals(d._tag, str(tag))

    def test_constructor_branch_and_tag(self):
        branch = 'stable/havana'
        tag = 2013.2
        d = downloader.GitDownloader(self._uri, self._dst,
                                     branch=branch, tag=tag)
        self.assertEquals(d._branch, branch)
        self.assertEquals(d._tag, str(tag))
