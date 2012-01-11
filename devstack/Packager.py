# vim: tabstop=4 shiftwidth=4 softtabstop=4

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


"""
An abstraction that different packaging
frameworks (ie apt, yum) can inherit from
"""

import Logger
import Shell
from Shell import execute

LOG = Logger.getLogger("install.packager")


class Packager():
    def __init__(self):
        pass

    def install_batch(self, pkgs):
        raise NotImplementedError()

    def remove_batch(self, pkgs):
        raise NotImplementedError()
