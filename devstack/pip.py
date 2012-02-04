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


def _cmd_name(distro):
    #of course u know they have to change the name...
    if distro == settings.RHEL6:
        return 'pip-python'
    else:
        return 'pip'


def install(pips, distro):
    actions = list()
    pipnames = sorted(pips.keys())
    for name in pipnames:
        pipfull = name
        pipinfo = pips.get(name)
        if pipinfo and pipinfo.get('version'):
            version = str(pipinfo.get('version'))
            if version:
                pipfull = pipfull + "==" + version
        actions.append(pipfull)
    if actions:
        LOG.info("Installing python packages [%s]" % (", ".join(actions)))
        root_cmd = _cmd_name(distro)
        cmd = [root_cmd, 'install'] + PIP_INSTALL_CMD_OPTS + actions
        sh.execute(*cmd, run_as_root=True)


def uninstall(pips, distro):
    pipnames = sorted(pips.keys())
    LOG.info("Uninstalling python packages [%s]" % (", ".join(pipnames)))
    for name in pipnames:
        pipinfo = pips.get(name, dict())
        skip_errors = pipinfo.get('skip_uninstall_errors', True)
        try:
            root_cmd = _cmd_name(distro)
            cmd = [root_cmd, 'uninstall'] + PIP_UNINSTALL_CMD_OPTS + [name]
            sh.execute(*cmd, run_as_root=True)
        except excp.ProcessExecutionError:
            if skip_errors:
                LOG.warn("Ignoring execution error that occured when uninstalling pip %s!" % (name))
            else:
                raise
