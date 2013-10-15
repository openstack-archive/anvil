import re
import unittest

from anvil import exceptions


class TestYamlException(unittest.TestCase):

    def test_YamlException(self):
        self.assertTrue(issubclass(exceptions.YamlException,
                                   exceptions.ConfigException))

    def test_YamlOptException(self):
        self.assertTrue(issubclass(exceptions.YamlOptException,
                                   exceptions.YamlException))
        exc = exceptions.YamlOptException('conf-sample', 'opt-sample',
                                          'ref-conf', 'ref-opt')

        self.assertTrue(re.search(r"`conf-sample`", str(exc)))
        self.assertTrue(re.search(r"`ref-opt`", str(exc)))
        self.assertTrue(re.search(r"opt-sample", str(exc)))
        self.assertTrue(re.search(r"ref-conf:ref-opt", str(exc)))

    def test_YamlConfException(self):
        self.assertTrue(issubclass(exceptions.YamlConfException,
                                   exceptions.YamlException))
        exc = exceptions.YamlConfException("no/such//path/to/yaml")

        self.assertTrue(re.search(r"no/such//path/to/yaml", str(exc)))

    def test_YamlLoopException(self):
        self.assertTrue(issubclass(exceptions.YamlLoopException,
                                   exceptions.YamlException))
        exc = exceptions.YamlLoopException('conf-sample', 'opt-sample',
                                           [('s1', 'r1'), ('s2', 'r2')])

        self.assertTrue(re.search(r"`conf-sample`", str(exc)))
        self.assertTrue(re.search(r"`opt-sample`", str(exc)))
        self.assertTrue(re.search(r"loop found", str(exc)))
        self.assertTrue(re.search(r"s1 => r1", str(exc)))
        self.assertTrue(re.search(r"s2 => r2", str(exc)))
