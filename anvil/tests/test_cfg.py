import os
import shutil
import tempfile
import unittest

from anvil import cfg
from anvil import exceptions
from anvil import shell
from anvil import utils


class TestYamlRefLoader(unittest.TestCase):

    def setUp(self):
        super(TestYamlRefLoader, self).setUp()

        self.sample = ""
        self.sample2 = ""
        self.sample3 = ""

        self.temp_dir = tempfile.mkdtemp()
        self.loader = cfg.YamlRefLoader(self.temp_dir)

    def tearDown(self):
        super(TestYamlRefLoader, self).tearDown()

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        del self.loader

    def _write_samples(self):
        with open(os.path.join(self.temp_dir, 'sample.yaml'), 'w') as f:
            f.write(self.sample)

        with open(os.path.join(self.temp_dir, 'sample2.yaml'), 'w') as f:
            f.write(self.sample2)

        with open(os.path.join(self.temp_dir, 'sample3.yaml'), 'w') as f:
            f.write(self.sample3)

    def test_load__default(self):
        self.sample = "default: default_value"
        self._write_samples()

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({'default': 'default_value'})
        self.assertEqual(processed, should_be)

    def test_load__empty(self):
        self.sample = ""
        self._write_samples()

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict()
        self.assertEqual(processed, should_be)

    def test_load__empty2(self):
        self.sample = "empty: "
        self._write_samples()

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({'empty': None})
        self.assertEqual(processed, should_be)

    def test_load__integer(self):
        self.sample = "integer: 11"
        self._write_samples()

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({'integer': 11})
        self.assertEqual(processed, should_be)

    def test_load__string(self):
        self.sample = 'string: "string sample"'
        self._write_samples()

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({'string': "string sample"})
        self.assertEqual(processed, should_be)

    def test_load__float(self):
        self.sample = "float: 1.1234"
        self._write_samples()

        processed = self.loader.load('sample')
        self.assertAlmostEqual(processed['float'], 1.1234)

    def test_load__bool(self):
        self.sample = "bool: true"
        self._write_samples()

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({'bool': True})
        self.assertEqual(processed, should_be)

    def test_load__list(self):
        self.sample = """
        list:
          - first
          - second
          - 100
        """
        self._write_samples()

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({'list': ['first', 'second', 100]})
        self.assertEqual(processed, should_be)

    def test_load__dict(self):
        self.sample = """
        dict:
          integer: 11
          default: default_value
          string: "string sample"
        """
        self._write_samples()

        # Note: dictionaries are always sorted by options names.
        processed = self.loader.load('sample')
        should_be = utils.OrderedDict([
            ('dict',
                utils.OrderedDict([
                    ('default', 'default_value'),
                    ('integer', 11),
                    ('string', 'string sample')
                ]))
        ])
        self.assertEqual(processed, should_be)

    def test_load__nested_dict(self):
        self.sample = """
        dict:
          dict1:
            default: default_value
            integer: 11

          dict2:
            default: default_value
            string: "string sample"
        """
        self._write_samples()

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
        self.sample = """
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

        self._write_samples()

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
        self.sample = 'opt: $(sample2:opt)'
        self.sample2 = 'opt: 10'
        self._write_samples()

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict({'opt': 10})
        self.assertEqual(processed, should_be)

    def test_load__self_reference(self):
        self.sample = """
        opt1: "$(sample:opt2)"
        opt2: "$(sample:opt3)"
        opt3: 10
        """
        self._write_samples()

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict([('opt1', 10), ('opt2', 10), ('opt3', 10)])
        self.assertEqual(processed, should_be)

    def test_load__auto_reference(self):
        self.sample = """
        ip: "$(auto:ip)"
        host: "$(auto:hostname)"
        home: "$(auto:home)"
        """
        self._write_samples()

        processed = self.loader.load('sample')

        self.assertTrue(isinstance(processed, utils.OrderedDict))
        self.assertEqual(len(processed), 3)
        self.assertEqual(processed['ip'], utils.get_host_ip())
        self.assertEqual(processed['host'], shell.hostname())
        self.assertEqual(processed['home'], shell.gethomedir())

    def test_load__multi_reference(self):
        self.sample = """
        multi_ref: "9 + $(sample2:opt) + $(sample3:opt) + $(auto:home) + 12"
        """
        self.sample2 = """opt: 10"""
        self.sample3 = """opt: 11"""

        self._write_samples()

        processed = self.loader.load('sample')

        self.assertTrue(isinstance(processed, utils.OrderedDict))
        self.assertEqual(len(processed), 1)
        self.assertEqual(processed['multi_ref'],
                         "9 + 10 + 11 + " + shell.gethomedir() + " + 12")

    def test_load__dict_reference(self):
        self.sample = """
        sample2:
            opt: "$(sample2:opt)"
        """
        self.sample2 = """opt: 10"""

        self._write_samples()

        processed = self.loader.load('sample')
        should_be = utils.OrderedDict([
            ('sample2', utils.OrderedDict([
                ('opt', 10)
            ]))
        ])
        self.assertEqual(processed, should_be)

    def test_load__complex_reference(self):
        # Fixme: changing `x_list` to `list` causes incorrect values. fix
        # this order influence.

        self.sample = """
        stable: 9

        ref0: "$(sample:stable)"
        ref1: "$(sample2:stable)"
        ref2: "$(sample2:ref1)"
        ref3: "$(sample2:ref2)"
        ref4: "$(sample2:ref3)"
        ref5: "$(sample3:ref1)"

        sample:
            stable: "$(sample:stable)"
            ref0: "$(sample:ref0)"
            ref1: "$(sample:ref1)"

        sample2:
          stable: "$(sample2:stable)"
          ref3: "$(sample2:ref3)"

        sample3:
          stable: "$(sample3:stable)"
          ref1: "$(sample3:ref1)"

        x_list:
          - "$(sample:sample2)"
          - "$(sample:sample3)"

        x_dict:
          sample3: "$(sample:sample3)"
          sample2: "$(sample:sample2)"
        """

        self.sample2 = """
        stable: 10
        ref1: "$(sample:stable)"
        ref2: "$(sample3:stable)"
        ref3: "$(sample3:ref1)"
        ref4: "$(sample2:stable)"
        """

        self.sample3 = """
        stable: 11
        ref1: "$(sample:stable)"
        """
        self._write_samples()

        processed = self.loader.load('sample')

        self.assertTrue(isinstance(processed, utils.OrderedDict))
        #self.assertEqual(len(processed), 11)
        self.assertEqual(processed['stable'], 9)
        self.assertEqual(processed['ref0'], 9)
        self.assertEqual(processed['ref1'], 10)
        self.assertEqual(processed['ref2'], 9)
        self.assertEqual(processed['ref3'], 11)
        self.assertEqual(processed['ref4'], 9)
        self.assertEqual(processed['ref5'], 9)

        sample = utils.OrderedDict([
            ('ref0', 9),
            ('ref1', 10),
            ('stable', 9),
        ])
        self.assertEqual(processed['sample'], sample)

        sample2 = utils.OrderedDict([
            ('ref3', 9),
            ('stable', 10),
        ])
        self.assertEqual(processed['sample2'], sample2)

        sample3 = utils.OrderedDict([
            ('ref1', 9),
            ('stable', 11),
        ])
        self.assertEqual(processed['sample3'], sample3)

        self.assertEqual(processed['x_list'], [sample2, sample3])
        self.assertEqual(
            processed['x_dict'],
            utils.OrderedDict([
                ('sample2', sample2),
                ('sample3', sample3),
            ])
        )

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

    def test_load__raises_no_option(self):
        self.sample = "ref: $(sample2:no-such-opt)"
        self.sample2 = ""
        self._write_samples()

        self.assertRaises(exceptions.YamlOptionNotFoundException,
                          self.loader.load, 'sample')

    def test_load__raises_no_config(self):
        self.sample = "ref: $(no-sush-conf:opt)"
        self.sample2 = ""
        self._write_samples()

        self.assertRaises(exceptions.YamlConfigNotFoundException,
                          self.loader.load, 'sample')

    def test_load__raises_loop(self):
        self.sample = "opt: $(sample2:opt)"
        self.sample2 = "opt: $(sample:opt)"
        self._write_samples()

        self.assertRaises(exceptions.YamlLoopException,
                          self.loader.load, 'sample')

    def test_load__raises_self_loop(self):
        self.sample = "opt: $(sample:opt)"
        self._write_samples()

        self.assertRaises(exceptions.YamlLoopException,
                          self.loader.load, 'sample')

        self.sample = """
        opt:
          - $(sample:opt)
        """
        self._write_samples()

        self.assertRaises(exceptions.YamlLoopException,
                          self.loader.load, 'sample')

        self.sample = """
        opt:
          opt: $(sample:opt)
        """
        self._write_samples()

        self.assertRaises(exceptions.YamlLoopException,
                          self.loader.load, 'sample')
