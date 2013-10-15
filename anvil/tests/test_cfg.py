import os
import shutil
import unittest

from anvil import cfg
from anvil import exceptions
from anvil import settings
from anvil import utils


class TestYamlRefLoader(unittest.TestCase):

    def setUp(self):
        if not os.path.exists(settings.TESTING_DIR):
            os.mkdir(settings.TESTING_DIR)

        self.sample = ""
        self.sample2 = ""
        self.sample3 = ""

        self.sample_path = os.path.join(settings.TESTING_DIR, 'sample.yaml')
        self.sample2_path = os.path.join(settings.TESTING_DIR, 'sample2.yaml')
        self.sample3_path = os.path.join(settings.TESTING_DIR, 'sample3.yaml')

        self.loader = cfg.YamlRefLoader(settings.TESTING_DIR)

    def tearDown(self):
        del self.loader
        shutil.rmtree(settings.TESTING_DIR, ignore_errors=True)

    def _write_yamls(self):
        with open(self.sample_path, 'w') as f:
            f.write(self.sample)

        with open(self.sample2_path, 'w') as f:
            f.write(self.sample2)

        with open(self.sample3_path, 'w') as f:
            f.write(self.sample3)

    def test_load__default(self):
        with open(self.sample_path, 'w') as f:
            f.write("default: default_value")

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({'default': 'default_value'})
        self.assertEqual(processed, should_be)

    def test_load__empty(self):
        with open(self.sample_path, 'w') as f:
            f.write("")

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict()
        self.assertEqual(processed, should_be)

    def test_load__empty2(self):
        with open(self.sample_path, 'w') as f:
            f.write("empty: ")

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({'empty': None})
        self.assertEqual(processed, should_be)

    def test_load__integer(self):
        with open(self.sample_path, 'w') as f:
            f.write("integer: 11")

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({'integer': 11})
        self.assertEqual(processed, should_be)

    def test_load__string(self):
        with open(self.sample_path, 'w') as f:
            f.write('string: "string sample"')

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({'string': "string sample"})
        self.assertEqual(processed, should_be)

    def test_load__float(self):
        with open(self.sample_path, 'w') as f:
            f.write("float: 1.1234")

        processed = self.loader.load('sample')
        self.assertAlmostEqual(processed['float'], 1.1234)

    def test_load__bool(self):
        with open(self.sample_path, 'w') as f:
            f.write("bool: true")

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({'bool': True})
        self.assertEqual(processed, should_be)

    def test_load__list(self):
        list_opt = """
        list:
          - first
          - second
          - 100
        """
        with open(self.sample_path, 'w') as f:
            f.write(list_opt)

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({'list': ['first', 'second', 100]})
        self.assertEqual(processed, should_be)

    def test_load__dict(self):
        dict_opt = """
        dict:
          default: default_value
          integer: 11
          string: "string sample"
        """

        with open(self.sample_path, 'w') as f:
            f.write(dict_opt)

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({
            'dict': {
                'default': 'default_value',
                'integer': 11,
                'string': 'string sample'
            }
        })
        self.assertEqual(processed, should_be)

    def test_load__nested_dict(self):

        nested_dict_opt = """
        dict:
          dict1:
            default: default_value
            integer: 11

          dict2:
            default: default_value
            string: "string sample"
        """

        with open(self.sample_path, 'w') as f:
            f.write(nested_dict_opt)

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({
            'dict': {
                'dict1': {'default': 'default_value',
                          'integer': 11},
                'dict2': {'default': 'default_value',
                          'string': 'string sample'}
            }
        })
        self.assertEqual(processed, should_be)

    def test_load__complex(self):

        complex_opt = """
        # some comments...

        integer: 15
        bool-opt: false
        bool-opt2: 0
        bool-opt3: 1
        float: 0.15

        list:
          - 1st
          - 2nd
          - 0.1
          - 100
          - true

        dict:

          dict1:
            default: default_value 1
            integer: 11
            bool: true

          dict2:
            default: default_value 2

        """

        with open(self.sample_path, 'w') as f:
            f.write(complex_opt)

        processed = self.loader.load('sample')

        self.assertEqual(len(processed), 7)
        self.assertEqual(processed['integer'], 15)
        self.assertEqual(processed['bool-opt'], False)
        self.assertEqual(processed['bool-opt2'], False)
        self.assertEqual(processed['bool-opt3'], True)
        self.assertAlmostEqual(processed['float'], 0.15)

        self.assertEqual(processed['list'], ['1st', '2nd', 0.1, 100, True])

        self.assertEqual(processed['dict']['dict1']['integer'], 11)
        self.assertEqual(processed['dict']['dict1']['bool'], True)
        self.assertEqual(processed['dict']['dict1']['default'],
                         'default_value 1')

        self.assertEqual(processed['dict']['dict2']['default'],
                         'default_value 2')

    def test_load__simple_reference(self):
        with open(self.sample2_path, 'w') as f:
            f.write('opt: 10')

        with open(self.sample_path, 'w') as f:
            f.write('opt: $(sample2:opt)')

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({'opt': 10})
        self.assertEqual(processed, should_be)

    def test_load__self_reference(self):
        self_reference = """
        opt1: "$(sample:opt2)"
        opt2: "$(sample:opt3)"
        opt3: 10
        """
        with open(self.sample_path, 'w') as f:
            f.write(self_reference)

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict([('opt1', 10), ('opt2', 10), ('opt3', 10)])
        self.assertEqual(processed, should_be)

    def test_load__auto_reference(self):
        auto_reference = """
        ip: "$(auto:ip)"
        host: "$(auto:hostname)"
        home: "$(auto:home)"
        ext_home: "this-is-path-to-$(auto:home)"
        """
        with open(self.sample_path, 'w') as f:
            f.write(auto_reference)

        processed = self.loader.load('sample')

        self.assertTrue(isinstance(processed, utils.OrderedDict))
        self.assertEqual(len(processed), 4)
        self.assertEqual(processed['home'], '/root')
        self.assertEqual(processed['ext_home'], 'this-is-path-to-/root')

    def test_load__complex_reference(self):
        sample = """
        stable: 9

        ref0: "$(sample:stable)"
        ref1: "$(sample2:stable)"
        ref2: "$(sample2:ref1)"
        ref3: "$(sample2:ref2)"
        ref4: "$(sample2:ref3)"
        ref5: "$(sample3:ref1)"
        """

        sample2 = """
        stable: 10
        ref1: "$(sample:stable)"
        ref2: "$(sample3:stable)"
        ref3: "$(sample3:ref1)"
        ref4: "$(sample2:stable)"
        """

        sample3 = """
        stable: 11
        ref1: "$(sample:stable)"
        """
        with open(self.sample_path, 'w') as f:
            f.write(sample)

        with open(self.sample2_path, 'w') as f:
            f.write(sample2)

        with open(self.sample3_path, 'w') as f:
            f.write(sample3)

        processed = self.loader.load('sample')

        self.assertEqual(len(processed), 7)
        self.assertEqual(processed['stable'], 9)
        self.assertEqual(processed['ref0'], 9)
        self.assertEqual(processed['ref1'], 10)
        self.assertEqual(processed['ref2'], 9)
        self.assertEqual(processed['ref3'], 11)
        self.assertEqual(processed['ref4'], 9)
        self.assertEqual(processed['ref5'], 9)

        processed = self.loader.load('sample2')

        self.assertEqual(len(processed), 5)
        self.assertEqual(processed['stable'], 10)
        self.assertEqual(processed['ref1'], 9)
        self.assertEqual(processed['ref2'], 11)
        self.assertEqual(processed['ref3'], 9)
        self.assertEqual(processed['ref4'], 10)

        processed = self.loader.load('sample3')
        self.assertEqual(len(processed), 2)
        self.assertEqual(processed['stable'], 11)
        self.assertEqual(processed['ref1'], 9)

    def test_load__raises_YamlOptException(self):
        sample = "ref: $(sample2:no-such-opt)"
        sample2 = ""

        with open(self.sample_path, 'w') as f:
            f.write(sample)

        with open(self.sample2_path, 'w') as f:
            f.write(sample2)

        self.assertRaises(exceptions.YamlOptException,
                          self.loader.load, 'sample')

    def test_load__raises_YamlConfException(self):
        sample = "ref: $(no-sush-conf:opt)"
        sample2 = ""

        with open(self.sample_path, 'w') as f:
            f.write(sample)

        with open(self.sample2_path, 'w') as f:
            f.write(sample2)

        self.assertRaises(exceptions.YamlConfException,
                          self.loader.load, 'sample')

    def test_load__raises_YamlLoopException(self):
        sample = "opt: $(sample2:opt)"
        sample2 = "opt: $(sample:opt)"

        with open(self.sample_path, 'w') as f:
            f.write(sample)

        with open(self.sample2_path, 'w') as f:
            f.write(sample2)

        self.assertRaises(exceptions.YamlLoopException,
                          self.loader.load, 'sample')
