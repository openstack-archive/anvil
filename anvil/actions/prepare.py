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
from anvil.actions import states
from anvil import colorizer
from anvil import log


LOG = log.getLogger(__name__)


class PrepareAction(action.Action):
    needs_sudo = False

    @property
    def lookup_name(self):
        return 'build'

    def _run(self, persona, groups):
        prior_groups = []
        for group, instances in groups:
            LOG.info("Preparing group %s...", colorizer.quote(group))
            dependency_handler_class = self.distro.dependency_handler_class
            dependency_handler = dependency_handler_class(self.distro,
                                                          self.root_dir,
                                                          instances.values(),
                                                          self.cli_opts,
                                                          group, prior_groups)
            removals = states.reverts("download")
            self._run_phase(
                action.PhaseFunctors(
                    start=lambda i: LOG.info('Downloading %s.', colorizer.quote(i.name)),
                    run=lambda i: i.download(),
                    end=lambda i, result: LOG.info("Performed %s downloads.", len(result))
                ),
                group,
                instances,
                "download",
                *removals
            )
            removals.extend(states.reverts("download-patch"))
            self._run_phase(
                action.PhaseFunctors(
                    start=lambda i: LOG.info('Post-download patching %s.', colorizer.quote(i.name)),
                    run=lambda i: i.patch("download"),
                    end=None,
                ),
                group,
                instances,
                "download-patch",
                *removals
            )
            dependency_handler.package_start()
            removals.extend(states.reverts("package"))
            if not hasattr(dependency_handler, 'package_instances'):
                self._run_phase(
                    action.PhaseFunctors(
                        start=lambda i: LOG.info("Packaging %s.", colorizer.quote(i.name)),
                        run=dependency_handler.package_instance,
                        end=None,
                    ),
                    group,
                    instances,
                    "package",
                    *removals
                )
            else:
                self._run_many_phase(
                    action.PhaseFunctors(
                        start=lambda i: LOG.info("Packaging %s.", colorizer.quote(i.name)),
                        run=dependency_handler.package_instances,
                        end=None,
                    ),
                    group,
                    instances,
                    "package",
                    *removals
                )
            dependency_handler.package_finish()
            prior_groups.append((group, instances))
