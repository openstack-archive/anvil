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
from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.components import base_install as binstall
from anvil.components import base_runtime as bruntime


LOG = logging.getLogger(__name__)


class OpenvswitchUninstaller(binstall.PkgUninstallComponent):

    def __init__(self, *args, **kwargs):
        binstall.PkgUninstallComponent.__init__(self, *args, **kwargs)
        self.runtime = self.siblings.get('running')

    def _del_bridge(self, name):
        cmd_template = self.distro.get_command('openvswitch', 'del_bridge')
        cmd = utils.expand_template_deep(cmd_template, {'NAME': name})
        try:
            sh.execute(cmd)
        except excp.ProcessExecutionError:
            LOG.warn("Failed to delete '%s' openvswitch bridge." % name)

    def pre_uninstall(self):
        bridges = self.get_option('bridges', default_value=[])
        if bridges:
            LOG.info("Attempting to delete %s bridges: %s."
                     % (colorizer.quote(self.name), ", ".join(bridges)))
            LOG.info("Ensuring %s service is started before we use it."
                     % colorizer.quote(self.name))
            self.runtime.start()
            self.runtime.wait_active()
            for bridge in bridges:
                self._del_bridge(bridge)


class OpenvswitchInstaller(binstall.PkgInstallComponent):

    def __init__(self, *args, **kwargs):
        binstall.PkgInstallComponent.__init__(self, *args, **kwargs)
        self.runtime = self.siblings.get('running')

    def _add_bridge(self, name):
        cmd_template = self.distro.get_command('openvswitch', 'add_bridge')
        cmd = utils.expand_template_deep(cmd_template, {'NAME': name})
        try:
            sh.execute(cmd)
        except excp.ProcessExecutionError:
            LOG.warn("Failed to create '%s' openvswitch bridge." % name)

    def post_install(self):
        binstall.PkgInstallComponent.post_install(self)

        bridges = self.get_option('bridges', default_value=[])
        if bridges:
            LOG.info("Attempting to create %s bridges: %s."
                     % (colorizer.quote(self.name), ", ".join(bridges)))
            LOG.info("Ensuring %s service is started before we use it."
                     % colorizer.quote(self.name))
            self.runtime.start()
            self.runtime.wait_active()
            for bridge in bridges:
                self._add_bridge(bridge)

    def configure(self):
        # NOTE(skudriashev): configuration is not required for this component
        pass

class OpenvswitchRuntime(bruntime.ServiceRuntime):

    @property
    def applications(self):
        return ["openvswitch"]

    def status_app(self, program):
        status_cmd = self.get_command("status", program)
        try:
            output = sh.execute(status_cmd, shell=True)[0]
        except excp.ProcessExecutionError:
            return False

        if utils.has_any(output, "is not running"):
            return False
        return True
