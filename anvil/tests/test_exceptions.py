import unittest

from anvil import exceptions


class TestYamlException(unittest.TestCase):

    def test_YamlException(self):
        self.assertTrue(issubclass(exceptions.YamlException,
                                   exceptions.ConfigException))

    def test_YamlOptionNotFoundException(self):
        self.assertTrue(issubclass(exceptions.YamlOptionNotFoundException,
                                   exceptions.YamlException))

        exc = str(
            exceptions.YamlOptionNotFoundException(
                ('conf-sample', 'opt-sample', 1),
                ('ref-conf', 'ref-opt', 'ref-sub-opt', 0)
            )
        )
        self.assertTrue("conf-sample" in exc)
        self.assertTrue("ref-opt" in exc)
        self.assertTrue("opt-sample" in exc)
        self.assertTrue("ref-conf:ref-opt:ref-sub-opt:0" in exc)

    def test_YamlConfigNotFoundException(self):
        self.assertTrue(issubclass(exceptions.YamlConfigNotFoundException,
                                   exceptions.YamlException))

        exc = str(exceptions.YamlConfigNotFoundException("no/such/path"))
        self.assertTrue("no/such/path" in exc)

    def test_YamlLoopException(self):
        self.assertTrue(issubclass(exceptions.YamlLoopException,
                                   exceptions.YamlException))

        exc = str(
            exceptions.YamlLoopException(
                ('conf-sample', 'opt-sample'),
                [('source', 'opt'), ('source', 'opt2'),
                 ('source', 'opt', 'sub_opt'), ('source', 0, 1)]
            )
        )
        self.assertTrue("`conf-sample => opt-sample`" in exc)
        self.assertTrue("loop found" in exc)
        self.assertTrue("`source => opt`" in exc)
        self.assertTrue("`source => opt2`" in exc)
        self.assertTrue("`source => opt => sub_opt`" in exc)
