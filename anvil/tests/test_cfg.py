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

import mock
import os
import shutil
import tempfile

from anvil import cfg
from anvil import exceptions
from anvil import shell
from anvil import test
from anvil import utils


class TestYamlRefLoader(test.TestCase):

    def setUp(self):
        super(TestYamlRefLoader, self).setUp()

        self.sample = ""
        self.sample2 = ""
        self.sample3 = ""

        self.temp_dir = tempfile.mkdtemp()
        self.loader = cfg.YamlRefLoader(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        del self.loader

        super(TestYamlRefLoader, self).tearDown()

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

        self.assertIsInstance(processed, utils.OrderedDict)
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

        self.assertIsInstance(processed, utils.OrderedDict)
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

    def test_load__wrapped_ref(self):
        self.sample = """
        stable: 23
        prefixed: "1$(sample:stable)"
        suffixed: "$(sample:stable)4"
        wrapped: "1$(sample:stable)4"
        """
        self._write_samples()
        processed = self.loader.load('sample')
        self.assertEqual(processed['prefixed'], "123")
        self.assertEqual(processed['suffixed'], "234")
        self.assertEqual(processed['wrapped'], "1234")

    def test_load__complex_reference(self):
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

        list:
          - "$(sample:sample2)"
          - "$(sample:sample3)"

        dict:
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

        self.assertIsInstance(processed, utils.OrderedDict)
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

        self.assertEqual(processed['list'], [sample2, sample3])
        self.assertEqual(
            processed['dict'],
            utils.OrderedDict([
                ('sample2', sample2),
                ('sample3', sample3),
            ])
        )

        processed = self.loader.load('sample2')

        self.assertEqual(processed, {
            'stable': 10,
            'ref1': 9,
            'ref2': 11,
            'ref3': 9,
            'ref4': 10,
        })

        processed = self.loader.load('sample3')
        self.assertEqual(len(processed), 2)
        self.assertEqual(processed['stable'], 11)
        self.assertEqual(processed['ref1'], 9)

    def test_load__magic_reference(self):
        self.sample = """
        magic:
          reference: $(sample:reference)

        reference: "$(sample:stable)"
        stable: 1
        """
        self._write_samples()
        processed = self.loader.load('sample')

        self.assertEqual(processed['stable'], 1)
        self.assertEqual(processed['reference'], 1)
        self.assertEqual(processed['magic']['reference'], 1)

    def test_load__more_complex_ref(self):
        """Test loading references links via dictionaries and lists."""

        self.sample = """
        stable: 9

        ref_to_s1: "$(sample:stable)"
        ref_to_s2: "$(sample2:stable)"
        ref_to_s3: "$(sample3:stable)"

        sample:
          stable: "$(sample:stable)"
          ref_to_s1: "$(sample:ref_to_s1)"
          ref_to_s2: "$(sample:ref_to_s2)"

        list:
          - "$(sample:stable)"
          - "$(sample2:stable)"
          - "$(sample3:stable)"
          - "$(sample:ref_to_s1)"
          - "$(sample:ref_to_s2)"
          - "$(sample:ref_to_s3)"
          - "$(sample:sample)"

        dict:
          stable: "$(sample:stable)"
          sample: "$(sample:sample)"
          list: "$(sample:list)"
        """

        self.sample2 = """stable: 10"""
        self.sample3 = """stable: 11"""
        self._write_samples()

        processed = self.loader.load('sample')

        self.assertEqual(processed['stable'], 9)
        self.assertEqual(processed['ref_to_s1'], 9)
        self.assertEqual(processed['ref_to_s2'], 10)
        self.assertEqual(processed['ref_to_s3'], 11)

        self.assertEqual(
            processed['sample'],
            utils.OrderedDict([('ref_to_s1', 9),
                               ('ref_to_s2', 10),
                               ('stable', 9)])
        )
        self.assertEqual(processed['list'], [9, 10, 11, 9, 10, 11,
                                             processed['sample']])
        self.assertEqual(
            processed['dict'],
            utils.OrderedDict([
                ('list', processed['list']),
                ('sample', processed['sample']),
                ('stable', 9),
            ])
        )

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

    def test_update_cache(self):
        self.sample = """
        stable: 9

        reference: "$(sample2:stable)"
        reference2: "$(sample2:stable)"
        reference3: "$(sample2:stable2)"
        """

        self.sample2 = """
        stable: 10
        stable2: 11
        """

        self._write_samples()

        self.loader.update_cache('sample', dict(reference=20))
        self.loader.update_cache('sample2', dict(stable=21))

        processed = self.loader.load('sample')
        self.assertEqual(processed['stable'], 9)
        self.assertEqual(processed['reference'], 20)
        self.assertEqual(processed['reference2'], 21)
        self.assertEqual(processed['reference3'], 11)

    def test_update_cache__few_times(self):
        self.sample = "stable: '$(sample2:stable)'"
        self.sample2 = "stable: 10"

        self._write_samples()

        processed = self.loader.load('sample')
        self.assertEqual(processed['stable'], 10)

        self.loader.update_cache('sample', dict(stable=11))
        processed = self.loader.load('sample')
        self.assertEqual(processed['stable'], 11)

        self.loader.update_cache('sample', dict(stable=12))
        processed = self.loader.load('sample')
        self.assertEqual(processed['stable'], 12)


class TestYamlMergeLoader(test.TestCase):

    def setUp(self):
        super(TestYamlMergeLoader, self).setUp()

        class Distro(object):

            def __init__(self):
                self.options = {
                    'unique-distro': True,
                    'redefined-in-general': 0,
                    'redefined-in-component': 0
                }

        class Persona(object):

            def __init__(self):
                self.component_options = {
                    'component': {
                        'unique-specific': True,
                        'redefined-in-specific': 1
                    }
                }

        self.general = ""
        self.component = ""
        self.distro = Distro()
        self.persona = Persona()

        self.temp_dir = tempfile.mkdtemp()

        with mock.patch('anvil.settings.COMPONENT_CONF_DIR', self.temp_dir):
            self.loader = cfg.YamlMergeLoader(self.temp_dir)

    def tearDown(self):
        super(TestYamlMergeLoader, self).tearDown()

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_samples(self):
        with open(os.path.join(self.temp_dir, 'general.yaml'), 'w') as f:
            f.write(self.general)

        with open(os.path.join(self.temp_dir, 'component.yaml'), 'w') as f:
            f.write(self.component)

    def test_load(self):
        self.general = """
        unique-general: True
        redefined-in-general: 1
        redefined-in-component: 1
        """

        self.component = """
        unique-component: True
        redefined-in-component: 2
        redefined-in-specific: 0
        """

        self._write_samples()

        merged = self.loader.load(self.distro, 'component', self.persona)
        should_be = utils.OrderedDict([
            ('app_dir', os.path.join(self.temp_dir, 'component', 'app')),
            ('component_dir', os.path.join(self.temp_dir, 'component')),
            ('root_dir', os.path.join(self.temp_dir)),
            ('trace_dir', os.path.join(self.temp_dir, 'component', 'traces')),

            ('unique-distro', True),
            ('redefined-in-general', 1),
            ('redefined-in-component', 2),
            ('redefined-in-specific', 1),

            ('unique-general', True),
            ('unique-specific', True),
            ('unique-component', True),
        ])
        self.assertEqual(merged, should_be)

        # yet once loading with changed values.
        self.persona.component_options['component']['redefined-in-specific'] = 2
        merged = self.loader.load(self.distro, 'component', self.persona)
        self.assertEqual(merged['redefined-in-specific'], 2)
