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


class TestTools(test.TestCase):
    def setUp(self):
        super(TestTools, self).setUp()
        self.multipip = sh.which("multipip", ['tools'])

    def _run_multipip(self, versions):
        cmd = [self.multipip]
        cmd.extend(versions)
        return sh.execute(cmd, check_exit_code=False)

    def test_multipip_ok(self):
        versions = [
            "x>1",
            "x>2",
        ]
        (stdout, stderr) = self._run_multipip(versions)
        stdout = stdout.strip()
        self.assertEqual("x>1,>2", stdout)
        self.assertEqual("", stderr.strip())

    def _extract_conflicts(self, stderr):
        conflicts = []
        in_conflict = False
        for line in stderr.splitlines():
            if line.startswith("Conflicting"):
                in_conflict = True
                continue
            if in_conflict and line.startswith("\t"):
                try:
                    line = line.lstrip()
                    where, req = line.split(":", 1)
                    conflicts.append(req.strip())
                except ValueError:
                    pass
            if in_conflict and not line.startswith("\t"):
                in_conflict = False
        return conflicts

    def test_multipip_best_pick(self):
        versions = [
            "x>1",
            "x>=2",
            "x!=2",
        ]
        (stdout, stderr) = self._run_multipip(versions)
        stdout = stdout.strip()
        self.assertEqual('x>1,!=2', stdout)
        self.assertEqual(["x>=2"], self._extract_conflicts(stderr))

    def test_multipip_best_pick_again(self):
        versions = [
            "x>1",
            "x>=2",
            "x!=2",
            'x>4',
            'x>5',
        ]
        (stdout, stderr) = self._run_multipip(versions)
        stdout = stdout.strip()
        self.assertEqual('x>1,!=2,>4,>5', stdout)
        self.assertEqual(["x>=2"], self._extract_conflicts(stderr))
