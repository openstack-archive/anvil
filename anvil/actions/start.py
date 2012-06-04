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

from anvil.actions import base

from anvil.actions.base import PhaseFunctors

LOG = log.getLogger(__name__)


class StartAction(base.Action):

    @staticmethod
    def get_lookup_name():
        return 'running'

    @staticmethod
    def get_action_name():
        return 'start'

    def _run(self, persona, component_order, instances):
        self._run_phase(
            PhaseFunctors(
                start=None,
                run=lambda i: i.configure(),
                end=None,
            ),
            component_order,
            instances,
            "Configure",
            )
        self._run_phase(
            PhaseFunctors(
                start=None,
                run=lambda i: i.pre_start(),
                end=None,
            ),
            component_order,
            instances,
            "Pre-start",
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Starting %s.', i.name),
                run=lambda i: i.start(),
                end=lambda i, result: LOG.info("Start %s applications", colorizer.quote(result)),
            ),
            component_order,
            instances,
            "Start"
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Post-starting %s.', colorizer.quote(i.name)),
                run=lambda i: i.post_start(),
                end=None,
            ),
            component_order,
            instances,
            "Post-start",
            )
        # Knock off anything connected to stopping
        self._delete_phase_files(['stop'])
