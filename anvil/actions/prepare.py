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
from anvil import colorizer
from anvil import log


LOG = log.getLogger(__name__)


class PrepareAction(action.Action):
    needs_sudo = False

    def __init__(self, name, distro, root_dir, cli_opts):
        action.Action.__init__(self, name, distro, root_dir, cli_opts)

    @property
    def lookup_name(self):
        return 'install'

    def _run(self, persona, component_order, instances):
        removals = []
        self._run_phase(
            action.PhaseFunctors(
                start=lambda i: LOG.info('Downloading %s.', colorizer.quote(i.name)),
                run=lambda i: i.download(),
                end=lambda i, result: LOG.info("Performed %s downloads.", len(result))
            ),
            component_order,
            instances,
            "download",
            *removals
            )
        self._run_phase(
            action.PhaseFunctors(
                start=lambda i: LOG.info('Post-download patching %s.', colorizer.quote(i.name)),
                run=lambda i: i.patch("download"),
                end=None,
            ),
            component_order,
            instances,
            "download-patch",
            *removals
            )
        self._run_phase(
            action.PhaseFunctors(
                start=lambda i: LOG.info('Preparing %s.', colorizer.quote(i.name)),
                run=lambda i: i.prepare(),
                end=None,
            ),
            component_order,
            instances,
            "prepare",
            *removals
            )
        dependency_handler = self.distro.dependency_handler_class(
            self.distro, self.root_dir, instances.values())
        general_package = "general"
        self._run_phase(
            action.PhaseFunctors(
                start=lambda i: LOG.info("Packing OpenStack and its dependencies"),
                run=lambda i: dependency_handler.package(),
                end=None,
            ),
            [general_package],
            {general_package: instances[general_package]},
            "package",
            *removals
            )
