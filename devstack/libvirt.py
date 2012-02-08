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
from devstack import settings
from devstack import shell as sh
from devstack import utils

LOG = logging.getLogger('devstack.libvirt')

#http://libvirt.org/uri.html
LIBVIRT_PROTOCOL_MAP = {
    'qemu': "qemu:///system",
    'kvm': "qemu:///system",
    'xen': 'xen:///',
}
VIRT_TYPE = 'libvirt'
VIRT_LIB = VIRT_TYPE
DEFAULT_VIRT = 'qemu'

#how libvirt is restarted
LIBVIRT_RESTART_CMD = {
    settings.RHEL6: ['service', 'libvirtd', 'restart'],
    settings.FEDORA16: ['service', 'libvirtd', 'restart'],
    #whyyyy??
    settings.UBUNTU11: ['service', 'libvirt-bin', 'restart'],
}

#how we check its status
LIBVIRT_STATUS_CMD = {
    settings.RHEL6: ['service', 'libvirtd', 'status'],
    settings.FEDORA16: ['service', 'libvirtd', 'status'],
    #whyyyy??
    settings.UBUNTU11: ['service', 'libvirt-bin', 'status'],
}

#status is either dead or alive!
_DEAD = 'DEAD'
_ALIVE = 'ALIVE'


def _get_virt_lib():
    #late import so that we don't always need this library to be active
    #ie if u aren't using libvirt in the first place
    return utils.import_module(VIRT_LIB)


def _status(distro):
    cmd = LIBVIRT_STATUS_CMD[distro]
    (sysout, _) = sh.execute(*cmd, run_as_root=False, check_exit_code=False)
    if sysout.find("running") != -1:
        return _ALIVE
    else:
        return _DEAD


def _destroy_domain(conn, dom_name):
    libvirt = _get_virt_lib()
    if not libvirt or not dom_name:
        return
    try:
        dom = conn.lookupByName(dom_name)
        LOG.debug("Destroying domain (%s) (id=%s) running %s" % (dom_name, dom.ID(), dom.OSType()))
        dom.destroy()
        dom.undefine()
    except libvirt.libvirtError, e:
        LOG.warn("Could not clear out libvirt domain (%s) due to [%s]" % (dom_name, e.message))


def restart(distro):
    if _status(distro) != _ALIVE:
        cmd = LIBVIRT_RESTART_CMD[distro]
        sh.execute(*cmd, run_as_root=True)


def default(virt_type):
    if not virt_type or not LIBVIRT_PROTOCOL_MAP.get(virt_type):
        return DEFAULT_VIRT
    else:
        return virt_type


def virt_ok(virt_type, distro):
    virt_protocol = LIBVIRT_PROTOCOL_MAP.get(virt_type)
    if not virt_protocol:
        return False
    #ensure we can do this
    restart(distro)
    #this is our sanity check to ensure that we can actually use that virt technology
    cmd = ['virsh', '-c', virt_protocol, 'uri']
    try:
        sh.execute(*cmd, run_as_root=True)
        return True
    except excp.ProcessExecutionError:
        return False


def clear_libvirt_domains(virt_type, inst_prefix):
    libvirt = _get_virt_lib()
    virt_protocol = LIBVIRT_PROTOCOL_MAP.get(virt_type)
    if not libvirt or not virt_protocol or not inst_prefix:
        return
    with sh.Rooted(True):
        LOG.info("Attempting to clear out leftover libvirt domains using protocol %s." % (virt_protocol))
        conn = None
        try:
            conn = libvirt.open(virt_protocol)
        except libvirt.libvirtError:
            LOG.warn("Could not connect to libvirt using protocol [%s]" % (virt_protocol))
        if conn:
            try:
                defined_domains = conn.listDefinedDomains()
                kill_domains = list()
                for domain in defined_domains:
                    if domain.startswith(inst_prefix):
                        kill_domains.append(domain)
                if kill_domains:
                    LOG.info("Found %s old domains to destroy (%s)" % (len(kill_domains), ", ".join(kill_domains)))
                    for domain in kill_domains:
                        _destroy_domain(conn, domain)
            except libvirt.libvirtError, e:
                LOG.warn("Could not clear out libvirt domains due to [%s]" % (e.message))
