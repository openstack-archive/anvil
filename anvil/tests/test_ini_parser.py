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

import StringIO
import unittest

from anvil import ini_parser


class TestAnvilConfigParser(unittest.TestCase):

    def setUp(self):
        super(TestAnvilConfigParser, self).setUp()
        self.config_parser = ini_parser.AnvilConfigParser()

    def tearDown(self):
        super(TestAnvilConfigParser, self).tearDown()
        del self.config_parser

    def _read_ini(self, ini):
        steam = StringIO.StringIO(ini)
        self.config_parser.readfp(steam)

    def test_commented_option_regexp_simple(self):
        regexp = self.config_parser.option_regex
        option = "# option1 = True"

        result = regexp.match(option)
        self.assertNotEqual(result, None)
        self.assertEqual(result.group(1), "option1")

    def test_commented_option_regexp_no_spaces(self):
        regexp = self.config_parser.option_regex
        option = "#option1=True"

        result = regexp.match(option)
        self.assertNotEqual(result, None)
        self.assertEqual(result.group(1), "option1")

    def test_commented_option_regexp_more_spaces(self):
        regexp = self.config_parser.option_regex
        option = "#    option1    =    True"

        result = regexp.match(option)
        self.assertNotEqual(result, None)
        self.assertEqual(result.group(1), "option1")

    def test_commented_option_regexp_with_spaces(self):
        regexp = self.config_parser.option_regex
        option = "#  option name  = option value"

        result = regexp.match(option)
        self.assertNotEqual(result, None)
        self.assertEqual(result.group(1), "option name")

    def test_readfp_comments_no_option(self):
        ini = """
[DEFAULT]
# comment line #1
# comment line #2

# comment line #3
"""
        self._read_ini(ini)

        # 7 global scope elements
        global_elements = self.config_parser.data._data.contents
        self.assertEquals(len(global_elements), 7)

    def test_readfp_comments_one_section(self):
        ini = """
[DEFAULT]
# comment line #1
# option1 = value1

# comment line #2
# option2 = value2
"""
        self._read_ini(ini)

        # 3 global scope elements
        global_elements = self.config_parser.data._data.contents
        self.assertEquals(len(global_elements), 3)

        # 6 lines in default section
        default_section = global_elements[1]
        self.assertEquals(len(default_section.contents), 6)

    def test_readfp_comments_several_section(self):
        ini = """
[DEFAULT]
# comment line #1
# option1 = value1

[ANOTHER_SECTION]
# comment line #1
# comment line #2
# option2 = value2
"""
        self._read_ini(ini)

        # 5 global scope elements
        global_elements = self.config_parser.data._data.contents
        self.assertEquals(len(global_elements), 5)

        # 3 lines in default section
        default_section = global_elements[1]
        self.assertEquals(len(default_section.contents), 3)

        # 4 lines in another section
        another_section = global_elements[3]
        self.assertEquals(len(another_section.contents), 4)

    def test_readfp_no_sections(self):
        ini = """
# comment line #1
# option1 = value1

# comment line #2
# option2 = value2
"""
        self._read_ini(ini)

        # 7 global scope elements
        global_elements = self.config_parser.data._data.contents
        self.assertEquals(len(global_elements), 7)

    def test_readfp_with_global_comment(self):
        ini = """
[DEFAULT]
# comment line #1
option1 = value1

# global scope comment

[ANOTHER_SECTION]
# comment line #2
option2 = value2
"""
        self._read_ini(ini)

        # 7 global scope elements
        global_elements = self.config_parser.data._data.contents
        self.assertEquals(len(global_elements), 7)

        # 3 lines in default section
        default_section = global_elements[1]
        self.assertEquals(len(default_section.contents), 3)

        # 3 lines in another section
        another_section = global_elements[5]
        self.assertEquals(len(another_section.contents), 3)

    def test_set_one_option_simple(self):
        ini = """
[DEFAULT]
# option1 = value1
# option2 = value2
"""
        pattern = """
[DEFAULT]
# option1 = value1
option1 = True
# option2 = value2
"""
        self._read_ini(ini)
        self.config_parser.set('DEFAULT', 'option1', 'True')

        output = StringIO.StringIO()
        self.config_parser.write(output)
        self.assertEquals(output.getvalue(), pattern)

    def test_set_one_option_same_commented(self):
        ini = """
[DEFAULT]
# comment line #1
# option1 = value1

# comment line #2
# option1 = value1

# comment line #3
# option2 = value2
"""
        pattern = """
[DEFAULT]
# comment line #1
# option1 = value1

# comment line #2
# option1 = value1
option1 = True

# comment line #3
# option2 = value2
"""
        self._read_ini(ini)
        self.config_parser.set('DEFAULT', 'option1', 'True')

        output = StringIO.StringIO()
        self.config_parser.write(output)
        self.assertEquals(output.getvalue(), pattern)

    def test_set_one_option_non_existent(self):
        ini = """
[DEFAULT]
# option1 = value1
# option2 = value2
"""
        pattern = """
[DEFAULT]
option3 = False
# option1 = value1
# option2 = value2
"""
        self._read_ini(ini)
        self.config_parser.set('DEFAULT', 'option3', 'False')

        output = StringIO.StringIO()
        self.config_parser.write(output)
        self.assertEquals(output.getvalue(), pattern)

    def test_set_several_options_complex(self):
        ini = """
[DEFAULT]
# option1 = value1
# option2 = value2
"""
        pattern = """
[DEFAULT]
option3 = False
# option1 = value1
option1 = True
# option2 = value2
option2 = False
"""
        self._read_ini(ini)
        self.config_parser.set('DEFAULT', 'option1', 'True')
        self.config_parser.set('DEFAULT', 'option2', 'False')
        self.config_parser.set('DEFAULT', 'option3', 'False')

        output = StringIO.StringIO()
        self.config_parser.write(output)
        self.assertEquals(output.getvalue(), pattern)
