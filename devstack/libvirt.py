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

from devstack import log as logging
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


def _get_virt_lib():
    return utils.import_module(VIRT_LIB)


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


def clear_libvirt_domains(virt_type, inst_prefix):
    #late import so that we don't always need this library to be active
    #ie if u aren't using libvirt in the first place
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
