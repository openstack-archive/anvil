# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
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

import collections
import json

from anvil import shell as sh


class Helper(object):
    def __init__(self):
        self._executable = sh.which("explode_envra", ["tools/"])

    def explode(self, *filenames):
        if not filenames:
            return []
        cmdline = [self._executable]
        for filename in filenames:
            cmdline.append(sh.basename(filename))
        (stdout, _stderr) = sh.execute(cmdline)
        results = []
        missing = collections.deque(filenames)
        for line in stdout.splitlines():
            decoded = json.loads(line)
            decoded['origin'] = missing.popleft()
            results.append(decoded)
        if missing:
            raise AssertionError("%s filenames names were lost during"
                                 " exploding: %s" % (len(missing),
                                                     list(missing)))
        if len(results) > len(filenames):
            diff = len(results) - len(filenames)
            raise AssertionError("%s filenames appeared unexpectedly while"
                                 " exploding" % (diff))
        return results
