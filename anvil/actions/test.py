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

from anvil import colorizer
from anvil import log

from anvil.actions import base as action

LOG = log.getLogger(__name__)


class TestAction(action.Action):
    @property
    def lookup_name(self):
        return 'test'

    def _run(self, persona, component_order, instances):
        dependency_handler_class = self.distro.dependency_handler_class
        dependency_handler = dependency_handler_class(self.distro,
                                                      self.root_dir,
                                                      instances.values())
        general_package = "general"
        self._run_phase(
            action.PhaseFunctors(
                start=lambda i: LOG.info("Installing packages"),
                run=lambda i: dependency_handler.install_all_deps(),
                end=None,
            ),
            [general_package],
            {general_package: instances[general_package]},
            "package-install-all-deps"
            # no removals
            )
        self._run_phase(
            action.PhaseFunctors(
                start=lambda i: LOG.info('Running tests of component %s.',
                                         colorizer.quote(i.name)),
                run=lambda i: i.run_tests(),
                end=None,
            ),
            component_order,
            instances,
            None,
            )
