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

from anvil import colorizer
from anvil import exceptions as excp
from anvil import importer
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

LOG = logging.getLogger(__name__)

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
    virt_type = str(virt_type).lower().strip()
    if virt_type not in LIBVIRT_PROTOCOL_MAP:
        return DEF_VIRT_TYPE
    else:
        return virt_type


class Virsh(object):

    def __init__(self, service_wait, distro):
        self.distro = distro
        self.wait_time = service_wait
        self.wait_attempts = 5

    def _service_status(self):
        cmd = self.distro.get_command('libvirt', 'status')
        (stdout, stderr) = sh.execute(cmd, check_exit_code=False)
        combined = (stdout + stderr)
        if combined.lower().find("running") != -1 or combined.lower().find('start') != -1:
            return (_ALIVE, combined)
        else:
            return (_DEAD, combined)

    def _destroy_domain(self, libvirt, conn, dom_name):
        try:
            dom = conn.lookupByName(dom_name)
            if dom:
                LOG.debug("Destroying domain (%r) (id=%s) running %r" % (dom_name, dom.ID(), dom.OSType()))
                dom.destroy()
                dom.undefine()
        except libvirt.libvirtError as e:
            LOG.warn("Could not clear out libvirt domain %s due to: %s", colorizer.quote(dom_name), e)

    def restart_service(self):
        cmd = self.distro.get_command('libvirt', 'restart')
        sh.execute(cmd)

    def wait_active(self):
        # TODO(harlowja) fix this by using the component wait active...
        started = False
        for _i in range(0, self.wait_attempts):
            (st, output) = self._service_status()
            if st != _ALIVE:
                LOG.info("Please wait %s seconds until libvirt is started.", self.wait_time)
                sh.sleep(self.wait_time)
            else:
                started = True
        if not started:
            raise excp.StartException("Unable to start the libvirt daemon due to: %s" % (output))

    def check_virt(self, virt_type):
        virt_protocol = LIBVIRT_PROTOCOL_MAP.get(virt_type)
        self.restart_service()
        self.wait_active()
        cmds = [{
            'cmd': self.distro.get_command('libvirt', 'verify'),
        }]
        mp = {
            'VIRT_PROTOCOL': virt_protocol,
            'VIRT_TYPE': virt_type,
        }
        utils.execute_template(*cmds, params=mp)

    def clear_domains(self, virt_type, inst_prefix):
        libvirt = None
        try:
            # A late import is done since this code could be used before libvirt is actually
            # installed, and that will cause the top level python import to fail which will
            # make anvil not work, so import it dynamically to bypass the previous mechanism
            libvirt = importer.import_module('libvirt')
        except RuntimeError as e:
            pass
        if not libvirt:
            LOG.warn("Could not clear out libvirt domains, libvirt not available for python.")
            return
        virt_protocol = LIBVIRT_PROTOCOL_MAP.get(virt_type)
        if not virt_protocol:
            LOG.warn("Could not clear out libvirt domains, no known protocol for virt type: %s", colorizer.quote(virt_type))
            return
        LOG.info("Attempting to clear out leftover libvirt domains using protocol: %s", colorizer.quote(virt_protocol))
        try:
            self.restart_service()
            self.wait_active()
        except (excp.StartException, IOError) as e:
            LOG.warn("Could not restart the libvirt daemon due to: %s", e)
            return
        try:
            conn = libvirt.open(virt_protocol)
        except libvirt.libvirtError as e:
            LOG.warn("Could not connect to libvirt using protocol %s due to: %s", colorizer.quote(virt_protocol), e)
            return
        with contextlib.closing(conn) as ch:
            try:
                defined_domains = ch.listDefinedDomains()
                kill_domains = list()
                for domain in defined_domains:
                    if domain.startswith(inst_prefix):
                        kill_domains.append(domain)
                if kill_domains:
                    utils.log_iterable(kill_domains, logger=LOG,
                        header="Found %s old domains to destroy" % (len(kill_domains)))
                    for domain in sorted(kill_domains):
                        self._destroy_domain(libvirt, ch, domain)
            except libvirt.libvirtError, e:
                LOG.warn("Could not clear out libvirt domains due to: %s", e)
