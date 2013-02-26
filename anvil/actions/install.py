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

from anvil import action
from anvil import colorizer
from anvil import components
from anvil import log
from anvil import shell as sh
from anvil import utils

from anvil.action import PhaseFunctors

LOG = log.getLogger(__name__)


class InstallAction(action.Action):
    def __init__(self, name, distro, root_dir, cli_opts):
        action.Action.__init__(self, name, distro, root_dir, cli_opts)
        self.only_configure = cli_opts.get('only_configure')

    @property
    def lookup_name(self):
        return 'install'

    def _on_finish(self, persona, component_order, instances):
        action.Action._on_finish(self, persona, component_order, instances)
        self._write_exports(component_order, instances, sh.joinpths("/etc/anvil",
                                                                    "%s.rc" % (self.name)))

    def _write_exports(self, component_order, instances, path):
        entries = []
        contents = StringIO()
        contents.write("# Exports for action %s\n\n" % (self.name))
        for c in component_order:
            exports = instances[c].env_exports
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

    def _analyze_dependencies(self, instance_dependencies):
        LOG.debug("Full known dependency list: %s", instance_dependencies)

    def _run(self, persona, component_order, instances):
        removals = []
        self._run_phase(
            PhaseFunctors(
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
            PhaseFunctors(
                start=lambda i: LOG.info('Post-download patching %s.', colorizer.quote(i.name)),
                run=lambda i: i.patch("download"),
                end=None,
            ),
            component_order,
            instances,
            "download-patch",
            *removals
            )

        removals += ['uninstall', 'unconfigure']
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Configuring %s.', colorizer.quote(i.name)),
                run=lambda i: i.configure(),
                end=None,
            ),
            component_order,
            instances,
            "configure",
            *removals
            )

        if self.only_configure:
            # TODO(harlowja) this could really be a new action that
            # does the download and configure and let the install
            # routine actually do the install steps...
            LOG.info("Exiting early, only asked to download and configure!")
            return

        all_instance_dependencies = {}

        def preinstall_run(instance):
            instance.pre_install()
            instance_dependencies = {}
            if isinstance(instance, (components.PkgInstallComponent)):
                instance_dependencies['packages'] = instance.packages
            if isinstance(instance, (components.PythonInstallComponent)):
                instance_dependencies['pips'] = instance.pip_requires
            all_instance_dependencies[instance.name] = instance_dependencies

        removals += ['pre-uninstall', 'post-uninstall']
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Preinstalling %s.', colorizer.quote(i.name)),
                run=preinstall_run,
                end=None,
            ),
            component_order,
            instances,
            "pre-install",
            *removals
            )

        # Do validation on the installed dependency set.
        self._analyze_dependencies(all_instance_dependencies)

        def install_start(instance):
            subsystems = set(list(instance.subsystems))
            if subsystems:
                utils.log_iterable(sorted(subsystems), logger=LOG,
                                   header='Installing %s using subsystems' % colorizer.quote(instance.name))
            else:
                LOG.info("Installing %s.", colorizer.quote(instance.name))

        def install_finish(instance, result):
            if not result:
                LOG.info("Finished install of %s.", colorizer.quote(instance.name))
            else:
                LOG.info("Finished install of %s with result %s.",
                         colorizer.quote(instance.name), result)

        self._run_phase(
            PhaseFunctors(
                start=install_start,
                run=lambda i: i.install(),
                end=install_finish,
            ),
            component_order,
            instances,
            "install",
            *removals
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Post-installing %s.', colorizer.quote(i.name)),
                run=lambda i: i.post_install(),
                end=None
            ),
            component_order,
            instances,
            "post-install",
            *removals
            )
