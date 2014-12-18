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

from StringIO import StringIO

import six

from anvil.actions import base as action
from anvil.actions import states
from anvil import colorizer
from anvil import log
from anvil import shell as sh
from anvil import utils


LOG = log.getLogger(__name__)


class InstallAction(action.Action):
    @property
    def lookup_name(self):
        return 'install'

    def _on_finish(self, persona, groups):
        action.Action._on_finish(self, persona, groups)
        self._write_exports(groups, sh.joinpths("/etc/anvil", "%s.rc" % (self.name)))

    def _write_exports(self, groups, path):
        entries = []
        contents = StringIO()
        contents.write("# Exports for action %s\n\n" % (self.name))
        for _group, instances in groups:
            for c, instance in six.iteritems(instances):
                exports = instance.env_exports
                if exports:
                    contents.write("# Exports for %s\n" % (c))
                    for (k, v) in exports.items():
                        export_entry = "export %s=%s" % (k, sh.shellquote(str(v).strip()))
                        entries.append(export_entry)
                        contents.write("%s\n" % (export_entry))
                    contents.write("\n")
        if entries:
            sh.write_file(path, contents.getvalue())
            utils.log_iterable(entries,
                               header="Wrote to %s %s exports" % (path, len(entries)),
                               logger=LOG)

    def _run(self, persona, groups):
        for group, instances in groups:
            dependency_handler_class = self.distro.dependency_handler_class
            dependency_handler = dependency_handler_class(self.distro,
                                                          self.root_dir,
                                                          instances.values(),
                                                          self.cli_opts)
            removals = states.reverts("pre-install")
            self._run_phase(
                action.PhaseFunctors(
                    start=lambda i: LOG.info('Preinstalling %s.', colorizer.quote(i.name)),
                    run=lambda i: i.pre_install(),
                    end=None,
                ),
                group,
                instances,
                "pre-install",
                *removals
            )
            removals.extend(states.reverts("package-install"))
            general_package = "general"
            if general_package in instances:
                self._run_phase(
                    action.PhaseFunctors(
                        start=lambda i: LOG.info("Installing packages"),
                        run=dependency_handler.install,
                        end=None,
                    ),
                    group,
                    {general_package: instances[general_package]},
                    "package-install",
                    *removals
                )
            removals.extend(states.reverts("configure"))
            self._run_phase(
                action.PhaseFunctors(
                    start=lambda i: LOG.info('Configuring %s.', colorizer.quote(i.name)),
                    run=lambda i: i.configure(),
                    end=None,
                ),
                group,
                instances,
                "configure",
                *removals
            )
            removals.extend(states.reverts("post-install"))
            self._run_phase(
                action.PhaseFunctors(
                    start=lambda i: LOG.info('Post-installing %s.', colorizer.quote(i.name)),
                    run=lambda i: i.post_install(),
                    end=None
                ),
                instances,
                "post-install",
                *removals
            )
