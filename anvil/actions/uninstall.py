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


class UninstallAction(action.Action):
    @property
    def lookup_name(self):
        return 'uninstall'

    def _order_components(self, components):
        components = super(UninstallAction, self)._order_components(components)
        components.reverse()
        return components

    def _run(self, persona, component_order, instances):
        removals = ['configure']
        self._run_phase(
            action.PhaseFunctors(
                start=lambda i: LOG.info('Unconfiguring %s.', colorizer.quote(i.name)),
                run=lambda i: i.unconfigure(),
                end=None,
            ),
            component_order,
            instances,
            'unconfigure',
            *removals
            )

        removals += ['post-install']
        self._run_phase(
            action.PhaseFunctors(
                start=None,
                run=lambda i: i.pre_uninstall(),
                end=None,
            ),
            component_order,
            instances,
            'pre-uninstall',
            *removals
            )

        removals += ['package-install', 'package-install-all-deps']
        general_package = "general"
        dependency_handler = self.distro.dependency_handler_class(
            self.distro, self.root_dir, instances.values())
        self._run_phase(
            action.PhaseFunctors(
                start=lambda i: LOG.info("Uninstalling packages"),
                run=lambda i: dependency_handler.uninstall(),
                end=None,
            ),
            [general_package],
            {general_package: instances[general_package]},
            "package-uninstall",
            *removals
            )
