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

import abc

from devstack import decorators
from devstack import log as logging
from devstack import utils

LOG = logging.getLogger("devstack.packager")


class Packager(object):
    __meta__ = abc.ABCMeta

    @decorators.log_debug
    def __init__(self, distro):
        self.distro = distro

    @abc.abstractmethod
    def install(self, pkg):
        pass

    @abc.abstractmethod
    def _remove(self, pkg):
        pass

    def remove(self, pkg):
        removable = pkg.get('removable', True)
        if not removable:
            return False
        return self._remove(pkg)

    def pre_install(self, pkg, params=None):
        cmds = pkg.get('pre-install')
        if cmds:
            LOG.info("Running pre-install commands for package %r.",
                     pkg['name'])
            utils.execute_template(*cmds, params=params)

    def post_install(self, pkg, params=None):
        cmds = pkg.get('post-install')
        if cmds:
            LOG.info("Running post-install commands for package %r.",
                     pkg['name'])
            utils.execute_template(*cmds, params=params)
