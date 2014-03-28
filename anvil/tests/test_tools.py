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

from anvil import shell as sh
from anvil import test
from anvil import utils

from nose_parameterized import parameterized


def load_examples():
    try:
        example_path = sh.joinpths("data", "tests", "requirements.yaml")
        examples = utils.load_yaml(example_path)
    except IOError:
        return []
    else:
        # The test generator will use the first element as the test identifer
        # so provide a index based test identifer to be able to connect test
        # failures to the example which caused it.
        return list(enumerate(examples))


class TestTools(test.TestCase):
    def setUp(self):
        super(TestTools, self).setUp()
        self.multipip = sh.which("multipip", ['tools'])

    def _run_multipip(self, versions):
        cmd = [self.multipip]
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

    @parameterized.expand(load_examples())
    def test_example(self, _name, example):
        (stdout, stderr) = self._run_multipip(example['requirements'])
        stdout = stdout.strip()
        self.assertEqual(example['expected'], stdout)
        if 'conflicts' in example:
            self.assertEqual(example['conflicts'],
                             self._extract_conflicts(stderr))
