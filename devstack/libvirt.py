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

import time

from devstack import exceptions as excp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

LOG = logging.getLogger('devstack.libvirt')

#http://libvirt.org/uri.html
LIBVIRT_PROTOCOL_MAP = {
    'qemu': "qemu:///system",
    'kvm': "qemu:///system",
    'xen': 'xen:///',
    'uml': 'uml:///system',
    'lxc': 'lxc:///',
}
VIRT_TYPE = 'libvirt'
VIRT_LIB = VIRT_TYPE

#distros name the libvirt service differently :-(
SV_NAME_MAP = {
    settings.RHEL6: 'libvirtd',
    settings.FEDORA16: 'libvirtd',
    settings.UBUNTU11: 'libvirt-bin',
}

#how libvirt is restarted
LIBVIRT_RESTART_CMD = ['service', '%SERVICE%', 'restart']

#how we check its status
LIBVIRT_STATUS_CMD = ['service', '%SERVICE%', 'status']

#this is just used to check that libvirt will work with
#a given protocol, may not be ideal but does seem to crap
#out if it won't work, so thats good
VIRSH_SANITY_CMD = ['virsh', '-c', '%VIRT_PROTOCOL%', 'uri']

#status is either dead or alive!
_DEAD = 'DEAD'
_ALIVE = 'ALIVE'

#alive wait time, just a sleep we put into so that the service can start up
WAIT_ALIVE_TIME = settings.WAIT_ALIVE_SECS


def _get_virt_lib():
    #late import so that we don't always need this library to be active
    #ie if u aren't using libvirt in the first place
    return utils.import_module(VIRT_LIB)


def _status(distro):
    cmds = list()
    cmds.append({
        'cmd': LIBVIRT_STATUS_CMD,
        'run_as_root': True,
    })
    mp = dict()
    mp['SERVICE'] = SV_NAME_MAP[distro]
    result = utils.execute_template(*cmds,
                                check_exit_code=False,
                                params=mp)
    if not result or not result[0]:
        return _DEAD
    (sysout, stderr) = result[0]
    combined = str(sysout) + str(stderr)
    combined = combined.lower()
    if combined.find("running") != -1 or combined.find('start') != -1:
        return _ALIVE
    else:
        return _DEAD


def _destroy_domain(libvirt, conn, dom_name):
    try:
        dom = conn.lookupByName(dom_name)
        LOG.debug("Destroying domain (%s) (id=%s) running %s" % (dom_name, dom.ID(), dom.OSType()))
        dom.destroy()
        dom.undefine()
    except libvirt.libvirtError, e:
        LOG.warn("Could not clear out libvirt domain (%s) due to [%s]" % (dom_name, e.message))


def restart(distro):
    if _status(distro) != _ALIVE:
        cmds = list()
        cmds.append({
            'cmd': LIBVIRT_RESTART_CMD,
            'run_as_root': True,
        })
        mp = dict()
        mp['SERVICE'] = SV_NAME_MAP[distro]
        utils.execute_template(*cmds, params=mp)
        LOG.info("Restarting the libvirt service, please wait %s seconds until its started." % (WAIT_ALIVE_TIME))
        time.sleep(WAIT_ALIVE_TIME)


def virt_ok(virt_type, distro):
    virt_protocol = LIBVIRT_PROTOCOL_MAP.get(virt_type)
    if not virt_protocol:
        return False
    try:
        restart(distro)
    except excp.ProcessExecutionError, e:
        LOG.warn("Could not restart libvirt on distro [%s] due to [%s]" % (distro, e.message))
        return False
    try:
        cmds = list()
        cmds.append({
            'cmd': VIRSH_SANITY_CMD,
            'run_as_root': True,
        })
        mp = dict()
        mp['VIRT_PROTOCOL'] = virt_protocol
        utils.execute_template(*cmds, params=mp)
        return True
    except excp.ProcessExecutionError, e:
        LOG.warn("Could check if libvirt was ok for protocol [%s] due to [%s]" % (virt_protocol, e.message))
        return False


def clear_libvirt_domains(distro, virt_type, inst_prefix):
    libvirt = _get_virt_lib()
    if not libvirt:
        LOG.warn("Could not clear out libvirt domains, libvirt not available for python.")
        return
    virt_protocol = LIBVIRT_PROTOCOL_MAP.get(virt_type)
    if not virt_protocol:
        LOG.warn("Could not clear out libvirt domains, no known protocol for virt type %s" % (virt_type))
        return
    with sh.Rooted(True):
        LOG.info("Attempting to clear out leftover libvirt domains using protocol %s" % (virt_protocol))
        try:
            restart(distro)
        except excp.ProcessExecutionError, e:
            LOG.warn("Could not restart libvirt on distro [%s] due to [%s]" % (distro, e.message))
            return
        try:
            conn = libvirt.open(virt_protocol)
        except libvirt.libvirtError, e:
            LOG.warn("Could not connect to libvirt using protocol [%s] due to [%s]" % (virt_protocol, e.message))
            return
        try:
            defined_domains = conn.listDefinedDomains()
            kill_domains = list()
            for domain in defined_domains:
                if domain.startswith(inst_prefix):
                    kill_domains.append(domain)
            if kill_domains:
                LOG.info("Found %s old domains to destroy (%s)" % (len(kill_domains), ", ".join(sorted(kill_domains))))
                for domain in sorted(kill_domains):
                    _destroy_domain(libvirt, conn, domain)
        except libvirt.libvirtError, e:
            LOG.warn("Could not clear out libvirt domains due to [%s]" % (e.message))
