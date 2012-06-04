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
from anvil import constants
from anvil import log

from anvil.actions import base

from anvil.actions.base import PhaseFunctors

LOG = log.getLogger(__name__)


class StatusAction(base.Action):

    @staticmethod
    def get_lookup_name():
        return 'running'

    @staticmethod
    def get_action_name():
        return 'status'

    def _fetch_status(self, component):
        return component.status()

    def _quote_status(self, status):
        if status == constants.STATUS_UNKNOWN:
            return colorizer.quote(status, quote_color='yellow')
        elif status == constants.STATUS_STARTED or status == constants.STATUS_INSTALLED:
            return colorizer.quote(status, quote_color='green')
        else:
            return colorizer.quote(status, quote_color='red')

    def _print_status(self, component, result):
        if isinstance(result, (dict)):
            LOG.info("Status of %s is:", colorizer.quote(component.name))
            for (name, status) in result.items():
                LOG.info("|-- %s --> %s.", colorizer.quote(name, quote_color='blue'), self._quote_status(status))
        elif isinstance(result, (list, set)):
            LOG.info("Status of %s is:", colorizer.quote(component.name))
            for status in result:
                LOG.info("|-- %s.", self._quote_status(status))
        else:
            LOG.info("Status of %s is %s.", colorizer.quote(component.name), self._quote_status(result))

    def _run(self, persona, component_order, instances):
        self._run_phase(
            PhaseFunctors(
                start=None,
                run=self._fetch_status,
                end=self._print_status,
            ),
            component_order,
            instances,
            None,
            )
