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
from anvil.actions import start
from anvil.actions import stop


class RestartAction(action.Action):

    def __init__(self, name, distro, root_dir, cli_opts):
        super(RestartAction, self).__init__(
            name, distro, root_dir, cli_opts.copy())
        self.start = start.StartAction(name, distro, root_dir, cli_opts.copy())
        self.stop = stop.StopAction(name, distro, root_dir, cli_opts.copy())

    @property
    def lookup_name(self):
        return 'running'

    def run(self, persona):
        self.stop.run(persona)
        self.start.run(persona)
