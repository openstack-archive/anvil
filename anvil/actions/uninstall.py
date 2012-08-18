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

from anvil import action
from anvil import colorizer
from anvil import log

from anvil.action import PhaseFunctors

LOG = log.getLogger(__name__)


# Which phase files we will remove
# at the completion of the given stage
KNOCK_OFF_MAP = {
    'uninstall': [
        'download',
    ],
    'unconfigure': [
        'configure',
    ],
    "post-uninstall": [
        'download', 'configure',
        'pre-install', 'install',
        'post-install',
    ],
}


class UninstallAction(action.Action):
    @property
    def lookup_name(self):
        return 'uninstall'

    def _order_components(self, components):
        components = super(UninstallAction, self)._order_components(components)
        components.reverse()
        return components

    def _run(self, persona, component_order, instances):
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Unconfiguring %s.', colorizer.quote(i.name)),
                run=lambda i: i.unconfigure(),
                end=None,
            ),
            component_order,
            instances,
            "Unconfigure"
            )
        self._run_phase(
            PhaseFunctors(
                start=None,
                run=lambda i: i.pre_uninstall(),
                end=None,
            ),
            component_order,
            instances,
            "Pre-uninstall",
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Uninstalling %s.', colorizer.quote(i.name)),
                run=lambda i: i.uninstall(),
                end=None,
            ),
            component_order,
            instances,
            "Uninstall"
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Post-uninstalling %s.', colorizer.quote(i.name)),
                run=lambda i: i.post_uninstall(),
                end=None,
            ),
            component_order,
            instances,
            "Post-uninstall",
            )

    def _get_opposite_stages(self, phase_name):
        return ('install', KNOCK_OFF_MAP.get(phase_name.lower(), []))
