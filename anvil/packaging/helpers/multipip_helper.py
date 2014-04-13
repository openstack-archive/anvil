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

import collections

import six

from anvil import shell as sh
from anvil import utils


class Helper(object):
    def __init__(self):
        self._multipip_executable = sh.which("multipip", ["tools/"])

    def _call_multipip(self, requirements,
                       requires_files=None, ignore_requirements=None):
        cmdline = [self._multipip_executable]
        if requires_files:
            cmdline.append("-r")
            cmdline.extend(requires_files)
        if ignore_requirements:
            cmdline.append("--ignore-package")
            cmdline.extend(ignore_requirements)
        if requirements:
            cmdline.append("--")
            cmdline.extend(requirements)
        (stdout, stderr) = sh.execute(cmdline, check_exit_code=False)
        compatibles = list(utils.splitlines_not_empty(stdout))
        incompatibles = collections.defaultdict(list)
        current_name = ''
        for line in stderr.strip().splitlines():
            if line.endswith(": incompatible requirements"):
                current_name = line.split(":", 1)[0].lower().strip()
                if current_name not in incompatibles:
                    incompatibles[current_name] = []
            else:
                incompatibles[current_name].append(line)
        cleaned_incompatibles = dict()
        for (requirement, lines) in six.iteritems(incompatibles):
            requirement = requirement.strip()
            if not requirement:
                continue
            if not lines:
                continue
            cleaned_incompatibles[requirement] = lines
        incompatibles = cleaned_incompatibles
        return (compatibles, incompatibles)

    def resolve(self, requirements,
                requires_files=None, ignore_requirements=None):
        return self._call_multipip(requirements,
                                   requires_files=requires_files,
                                   ignore_requirements=ignore_requirements)
