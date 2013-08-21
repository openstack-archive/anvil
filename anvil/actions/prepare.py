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
        self.jobs = cli_opts.get('jobs')

    @property
    def lookup_name(self):
        return 'install'

    def _run(self, persona, component_order, instances):
        dependency_handler_class = self.distro.dependency_handler_class
        dependency_handler = dependency_handler_class(self.distro,
                                                      self.root_dir,
                                                      instances.values(),
                                                      opts={"jobs": self.jobs})
        dependency_handler.post_bootstrap()

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
        removals += ["package-destroy"]
        dependency_handler.package_start()
        self._run_phase(
            action.PhaseFunctors(
                start=lambda i: LOG.info("Packaging %s.", colorizer.quote(i.name)),
                run=dependency_handler.package_instance,
                end=None,
            ),
            component_order,
            instances,
            "package",
            *removals
            )
        dependency_handler.package_finish()
