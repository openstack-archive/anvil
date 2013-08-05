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

# pylint: disable=R0915
from anvil.actions import base as action
from anvil import log


LOG = log.getLogger(__name__)


class BuildAction(action.Action):
    needs_sudo = True

    def __init__(self, name, distro, root_dir, cli_opts):
        action.Action.__init__(self, name, distro, root_dir, cli_opts)
        self.usr_only = cli_opts.get('usr_only')
        self.jobs = cli_opts.get('jobs')

    @property
    def lookup_name(self):
        return 'install'

    def _run(self, persona, component_order, instances):
        dependency_handler_class = self.distro.dependency_handler_class
        dependency_handler = dependency_handler_class(self.distro,
                                                      self.root_dir,
                                                      instances.values(),
                                                      opts={"usr_only": self.usr_only,
                                                            "jobs": self.jobs})
        dependency_handler.build_binary()
