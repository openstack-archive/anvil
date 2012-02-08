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


from devstack import exceptions as excp
from devstack import log as logging
from devstack import shell as sh
from devstack import settings

LOG = logging.getLogger("devstack.pip")
PIP_UNINSTALL_CMD_OPTS = ['-y', '-q']
PIP_INSTALL_CMD_OPTS = ['-q']

#the pip command is named different :-(
PIP_CMD_NAMES = {
    settings.RHEL6: 'pip-python',
    settings.FEDORA16: 'pip-python',
    settings.UBUNTU11: 'pip',
}


def install(pips, distro):
    pipnames = sorted(pips.keys())
    root_cmd = PIP_CMD_NAMES[distro]
    LOG.info("Installing python packages (%s) using command (%s)" % (", ".join(pipnames), root_cmd))
    for name in pipnames:
        pipfull = name
        pipinfo = pips.get(name)
        if pipinfo and pipinfo.get('version'):
            version = pipinfo.get('version')
            if version is not None:
                pipfull = pipfull + "==" + str(version)
        LOG.info("Installing python package (%s)" % (pipfull))
        real_cmd = [root_cmd, 'install']
        real_cmd += PIP_INSTALL_CMD_OPTS
        options = pipinfo.get('options')
        if options is not None:
            LOG.info("Using pip options: %s" % (str(options)))
            real_cmd += [str(options)]
        real_cmd += [pipfull]
        sh.execute(*real_cmd, run_as_root=True)


def uninstall(pips, distro, skip_errors=True):
    pipnames = sorted(pips.keys())
    root_cmd = PIP_CMD_NAMES[distro]
    LOG.info("Uninstalling python packages (%s) using command (%s)" % (", ".join(pipnames), root_cmd))
    for name in pipnames:
        try:
            cmd = [root_cmd, 'uninstall'] + PIP_UNINSTALL_CMD_OPTS + [name]
            sh.execute(*cmd, run_as_root=True)
        except excp.ProcessExecutionError:
            if skip_errors:
                LOG.warn("Ignoring execution error that occured when uninstalling pip %s!" % (name))
            else:
                raise
