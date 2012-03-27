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

import contextlib

from devstack import exceptions as excp
from devstack import importer
from devstack import log as logging
from devstack import shell as sh
from devstack import utils

LOG = logging.getLogger('devstack.libvirt')

# See: http://libvirt.org/uri.html
LIBVIRT_PROTOCOL_MAP = {
    'qemu': "qemu:///system",
    'kvm': "qemu:///system",
    'xen': 'xen:///',
    'uml': 'uml:///system',
    'lxc': 'lxc:///',
}

# Status is either dead or alive!
_DEAD = 'DEAD'
_ALIVE = 'ALIVE'

# Type that should always work
DEF_VIRT_TYPE = 'qemu'


def canon_libvirt_type(virt_type):
    if not virt_type:
        return DEF_VIRT_TYPE
    virt_type = virt_type.lower().strip()
    if not (virt_type in LIBVIRT_PROTOCOL_MAP):
        return DEF_VIRT_TYPE
    else:
        return virt_type


class Virsh(object):

    def __init__(self, config, distro):
        self.cfg = config
        self.distro = distro
        self.wait_time = max(self.cfg.getint('default', 'service_wait_seconds'), 1)

    def _service_status(self):
        cmd = self.distro.get_command('libvirt', 'status')
        (stdout, stderr) = sh.execute(*cmd, run_as_root=True, check_exit_code=False)
        combined = (stdout + stderr).lower()
        if combined.find("running") != -1 or combined.find('start') != -1:
            return _ALIVE
        else:
            return _DEAD

    def _destroy_domain(self, conn, dom_name):
        libvirt = importer.import_module('libvirt')
        try:
            dom = conn.lookupByName(dom_name)
            LOG.debug("Destroying domain (%r) (id=%s) running %r" % (dom_name, dom.ID(), dom.OSType()))
            dom.destroy()
            dom.undefine()
        except libvirt.libvirtError as e:
            LOG.warn("Could not clear out libvirt domain %r due to: %s" % (dom_name, e))

    def restart_service(self):
        if self._service_status() != _ALIVE:
            cmd = self.distro.get_command('libvirt', 'restart')
            sh.execute(*cmd, run_as_root=True)
            LOG.info("Restarting the libvirt service, please wait %s seconds until its started." % (self.wait_time))
            sh.sleep(self.wait_time)

    def check_virt(self, virt_type):
        virt_protocol = LIBVIRT_PROTOCOL_MAP.get(virt_type)
        self.restart_service()
        cmds = list()
        cmds.append({
            'cmd': self.distro.get_command('libvirt', 'verify'),
            'run_as_root': True,
        })
        mp = dict()
        mp['VIRT_PROTOCOL'] = virt_protocol
        mp['VIRT_TYPE'] = virt_type
        utils.execute_template(*cmds, params=mp)

    def clear_domains(self, virt_type, inst_prefix):
        libvirt = importer.import_module('libvirt')
        if not libvirt:
            LOG.warn("Could not clear out libvirt domains, libvirt not available for python.")
            return
        virt_protocol = LIBVIRT_PROTOCOL_MAP.get(virt_type)
        if not virt_protocol:
            LOG.warn("Could not clear out libvirt domains, no known protocol for virt type %r" % (virt_type))
            return
        with sh.Rooted(True):
            LOG.info("Attempting to clear out leftover libvirt domains using protocol %r" % (virt_protocol))
            try:
                self.restart_service()
            except excp.ProcessExecutionError as e:
                LOG.warn("Could not restart libvirt due to: %s" % (e))
                return
            try:
                conn = libvirt.open(virt_protocol)
            except libvirt.libvirtError as e:
                LOG.warn("Could not connect to libvirt using protocol %r due to: %s" % (virt_protocol, e))
                return
            with contextlib.closing(conn) as ch:
                try:
                    defined_domains = ch.listDefinedDomains()
                    kill_domains = list()
                    for domain in defined_domains:
                        if domain.startswith(inst_prefix):
                            kill_domains.append(domain)
                    if kill_domains:
                        LOG.info("Found %s old domains to destroy (%s)" % (len(kill_domains), ", ".join(sorted(kill_domains))))
                        for domain in sorted(kill_domains):
                            self._destroy_domain(ch, domain)
                except libvirt.libvirtError, e:
                    LOG.warn("Could not clear out libvirt domains due to %s" % (e))
