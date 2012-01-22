# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

LOG = logging.getLogger("devstack.pip")

INSTALL_CMD = ['pip', 'install']
UNINSTALL_CMD = ['pip', 'uninstall']


def install(pips):
    if(not pips or len(pips) == 0):
        return
    actions = list()
    pipnames = sorted(pips.keys())
    for name in pipnames:
        pipfull = name
        pipinfo = pips.get(name)
        if(pipinfo and pipinfo.get('version')):
            version = str(pipinfo.get('version'))
            if(len(version)):
                pipfull = pipfull + "==" + version
        actions.append(pipfull)
    if(len(actions)):
        LOG.info("Installing python packages [%s]" % (", ".join(actions)))
        cmd = INSTALL_CMD + actions
        sh.execute(*cmd, run_as_root=True)


def uninstall(pips):
    if(not pips or len(pips) == 0):
        return
    pipnames = sorted(pips.keys())
    LOG.info("Uninstalling python packages [%s]" % (", ".join(pipnames)))
    for name in pipnames:
        pipinfo = pips.get(name, dict())
        skip_errors = pipinfo.get('skip_uninstall_errors', False)
        try:
            cmd = UNINSTALL_CMD + [name]
            sh.execute(*cmd, run_as_root=True)
        except excp.ProcessExecutionError:
            if(skip_errors):
                LOG.warn("Ignoring execution error that occured when uninstalling %s!" % (name))
            else:
                raise
