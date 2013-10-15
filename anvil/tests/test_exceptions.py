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
