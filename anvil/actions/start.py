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


class StartAction(action.Action):
    @property
    def lookup_name(self):
        return 'running'

    def _run(self, persona, component_order, instances):
        self._run_phase(
            PhaseFunctors(
                start=None,
                run=lambda i: i.pre_start(),
                end=None,
            ),
            component_order,
            instances,
            "pre-start",
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Starting %s.', i.name),
                run=lambda i: i.start(),
                end=lambda i, result: LOG.info("Start %s applications", colorizer.quote(result)),
            ),
            component_order,
            instances,
            "start",
            'stopped'
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Post-starting %s.', colorizer.quote(i.name)),
                run=lambda i: i.post_start(),
                end=None,
            ),
            component_order,
            instances,
            "post-start",
            'stopped'
            )
