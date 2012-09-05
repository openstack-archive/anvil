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
from anvil import log
from anvil import shell as sh
from anvil import utils

from anvil.action import PhaseFunctors

LOG = log.getLogger(__name__)

# Which phase files we will remove
# at the completion of the given stage
KNOCK_OFF_MAP = {
    'configure': ['unconfigure'],
    'install': ['uninstall'],
    'post-install': [
        'unconfigure',
        'pre-uninstall', 
        'uninstall',
        "post-uninstall",
    ],
}


class InstallAction(action.Action):
    @property
    def lookup_name(self):
        return 'install'

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
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Downloading %s.', colorizer.quote(i.name)),
                run=lambda i: i.download(),
                end=lambda i, result: LOG.info("Performed %s downloads.", len(result))
            ),
            component_order,
            instances,
            "Download"
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Configuring %s.', colorizer.quote(i.name)),
                run=lambda i: i.configure(),
                end=None,
            ),
            component_order,
            instances,
            "Configure"
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Preinstalling %s.', colorizer.quote(i.name)),
                run=lambda i: i.pre_install(),
                end=None,
            ),
            component_order,
            instances,
            "Pre-install"
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

        self._run_phase(
            PhaseFunctors(
                start=install_start,
                run=lambda i: i.install(),
                end=install_finish,
            ),
            component_order,
            instances,
            "Install"
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Post-installing %s.', colorizer.quote(i.name)),
                run=lambda i: i.post_install(),
                end=None
            ),
            component_order,
            instances,
            "Post-install",
            )

    def _get_opposite_stages(self, phase_name):
        return ('uninstall', KNOCK_OFF_MAP.get(phase_name.lower(), []))
