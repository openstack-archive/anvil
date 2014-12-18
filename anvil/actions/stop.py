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
from anvil.actions import states

LOG = log.getLogger(__name__)


class StopAction(action.Action):
    @property
    def lookup_name(self):
        return 'running'

    def _order_components(self, components):
        components = super(StopAction, self)._order_components(components)
        components.reverse()
        return components

    def _run(self, persona, groups):
        for group, instances in groups:
            LOG.info("Stopping group %s...", colorizer.quote(group))
            removals = states.reverts("stopped")
            self._run_phase(
                action.PhaseFunctors(
                    start=lambda i: LOG.info('Stopping %s.', colorizer.quote(i.name)),
                    run=lambda i: i.stop(),
                    end=lambda i, result: LOG.info("Stopped %s application(s).",
                                                   colorizer.quote(result)),
                ),
                group,
                instances,
                "stopped",
                *removals
            )
