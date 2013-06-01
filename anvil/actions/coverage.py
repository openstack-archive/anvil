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

from anvil.actions import base as action
from anvil import colorizer
from anvil import log

LOG = log.getLogger(__name__)


class CoverageAction(action.Action):
    @property
    def lookup_name(self):
        return 'coverage'

    def _run(self, persona, component_order, instances):
        results = self._run_phase(
            action.PhaseFunctors(
                start=lambda i: LOG.info('Show tests coverage for component %s.', colorizer.quote(i.name)),
                run=lambda i: i.show_coverage(),
                end=None,
            ),
            component_order,
            instances,
            None,
            )
        error = [component.name for (component, rc) in results.items() if rc]
        if error:
            raise RuntimeError("Coverage errors in '%s' components" % ", ".join(error))
