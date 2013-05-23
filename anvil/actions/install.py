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
from anvil.actions import prepare

LOG = log.getLogger(__name__)


multipip_executable = "multipip"
py2rpm_executable = "py2rpm"
force_frozen = True


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

    def _run(self, persona, component_order, instances):
        removals = ['uninstall', 'unconfigure']
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

        def preinstall_run(instance):
            instance.pre_install()

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

        packages = {}
        for inst in instances.itervalues():
            if isinstance(inst, components.PkgInstallComponent):
                for pack in inst.packages:
                    packages[pack["name"]] = pack

        anvil_repo_filename = sh.joinpths(self.root_dir, "deps", "anvil.repo")
        with sh.Rooted(True):
            sh.copy(anvil_repo_filename, "/etc/yum.repos.d/")
        packages[prepare.OPENSTACK_DEPS_PACKAGE_NAME] = {
            "name": prepare.OPENSTACK_DEPS_PACKAGE_NAME
        }
        cmdline = ["yum", "erase", "-y", prepare.OPENSTACK_DEPS_PACKAGE_NAME]
        sh.execute(*cmdline, run_as_root=True)
        cmdline = ["yum", "clean", "all"]
        sh.execute(*cmdline, run_as_root=True)
        components.PkgInstallComponent.install_packages(
            packages.values(), self.distro, sh.joinpths(self.root_dir, "deps"))

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
