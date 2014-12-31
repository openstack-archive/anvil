# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2014 Yahoo! Inc. All Rights Reserved.
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

import glob
import re
import sys

from anvil.packaging.helpers import pip_helper
from anvil import shell as sh
from anvil import test
from anvil import utils

from nose_parameterized import parameterized

EXAMPLE_GLOB = sh.joinpths("data", "tests", "requirements*.yaml")


def load_examples():
    examples = []
    for filename in glob.glob(EXAMPLE_GLOB):
        if sh.isfile(filename):
            # The test generator will use the first element as the test
            # identifer so provide a filename + index based test identifer to
            # be able to connect test failures to the example which caused it.
            try:
                base = sh.basename(filename)
                base = re.sub(r"[.\s]", "_", base)
                for i, example in enumerate(utils.load_yaml(filename)):
                    examples.append(("%s_%s" % (base, i), example))
            except IOError:
                pass
    return examples


class TestTools(test.TestCase):
    def setUp(self):
        super(TestTools, self).setUp()
        self.multipip = [sys.executable, sh.which("multipip", ['tools'])]

    def _run_multipip(self, versions):
        cmd = list(self.multipip)
        cmd.extend(versions)
        return sh.execute(cmd, check_exit_code=False)

    def _extract_conflicts(self, stderr):
        conflicts = {}
        current_name = None
        capturing = False
        for line in stderr.splitlines():
            if line.endswith(": incompatible requirements"):
                capturing = False
                current_name = line.split(":", 1)[0].lower().strip()
                if current_name not in conflicts:
                    conflicts[current_name] = []
                continue
            if line.startswith("Choosing") and current_name:
                capturing = False
                continue
            if line.startswith("Conflicting") and current_name:
                capturing = True
                continue
            if capturing and current_name and line.startswith("\t"):
                try:
                    line = line.lstrip()
                    _where, req = line.split(":", 1)
                    req = req.strip()
                    if req:
                        conflicts[current_name].append(req)
                except ValueError:
                    pass
        return conflicts

    def assertEquivalentRequirements(self, expected, created):
        self.assertEqual(len(expected), len(created))
        for req in created:
            self.assertIn(req, expected)

    @parameterized.expand(load_examples())
    def test_example(self, _name, example):
        (stdout, stderr) = self._run_multipip(example['requirements'])
        expected_normalized = []
        for line in example['expected'].strip().splitlines():
            expected_normalized.append(pip_helper.extract_requirement(line))
        parsed_normalized = []
        for line in stdout.strip().splitlines():
            parsed_normalized.append(pip_helper.extract_requirement(line))
        self.assertEquivalentRequirements(expected_normalized,
                                          parsed_normalized)
        if 'conflicts' in example:
            self.assertEqual(example['conflicts'],
                             self._extract_conflicts(stderr))
