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

import psutil
import re
import weakref

from anvil import shell as sh
from anvil import utils

from anvil.components.configurators import nova as nconf
from anvil.components.helpers import virt as lv


def get_shared_params(ip, protocol,
                      api_host, api_port,
                      s3_host, s3_port,
                      ec2_host, ec2_port,
                      ec2_admin_host, ec2_admin_port, **kwargs):
    mp = {}
    mp['service_host'] = ip

    # Uri's of the various nova endpoints
    mp['endpoints'] = {
        'ec2_admin': {
            'uri': utils.make_url(protocol, ec2_admin_host, ec2_admin_port, "services/Admin"),
            'port': ec2_admin_port,
            'host': ec2_admin_host,
            'protocol': protocol,
        },
        'ec2_cloud': {
            'uri': utils.make_url(protocol, ec2_host, ec2_port, "services/Cloud"),
            'port': ec2_port,
            'host': ec2_host,
            'protocol': protocol,
        },
        's3': {
            'uri': utils.make_url(protocol, s3_host, s3_port),
            'port': s3_port,
            'host': s3_host,
            'protocol': protocol,
        },
        'api': {
            'uri': utils.make_url(protocol, api_host, api_port, "v2"),
            'port': api_port,
            'host': api_host,
            'protocol': protocol,
        },
    }

    return mp


class ComputeCleaner(object):
    def __init__(self, uninstaller):
        self.uninstaller = weakref.proxy(uninstaller)

    def clean(self):
        virsh = lv.Virsh(self.uninstaller.get_int_option('service_wait_seconds'), self.uninstaller.distro)
        virt_driver = utils.canon_virt_driver(self.uninstaller.get_option('virt_driver'))
        if virt_driver == 'libvirt':
            inst_prefix = self.uninstaller.get_option('instance_name_prefix', default_value='instance-')
            libvirt_type = lv.canon_libvirt_type(self.uninstaller.get_option('libvirt_type'))
            virsh.clear_domains(libvirt_type, inst_prefix)


class NetworkCleaner(object):
    def __init__(self, uninstaller):
        self.uninstaller = weakref.proxy(uninstaller)

    def _stop_dnsmasq(self):
        # Shutdown dnsmasq which is typically used by nova-network
        # to provide dhcp leases and since nova currently doesn't
        # seem to shut them down itself (why not?) we have to do it for it..
        #
        # TODO(harlowja) file a bug to get that fixed...
        to_kill = []
        for proc in psutil.process_iter():
            if proc.name.find("dnsmasq") == -1:
                continue
            cwd = ''
            cmdline = ''
            cwd = proc.getcwd()
            cmdline = " ".join(proc.cmdline)
            to_try = False
            for t in [cwd, cmdline]:
                if t.lower().find("nova") != -1:
                    to_try = True
            if to_try:
                to_kill.append(proc.pid)
        if len(to_kill):
            utils.log_iterable(to_kill,
                               header="Killing leftover nova dnsmasq processes with process ids",
                               logger=nconf.LOG)
            for pid in to_kill:
                sh.kill(pid)

    def _clean_iptables(self):
        # Nova doesn't seem to cleanup its iptables rules that it
        # establishes when it is removed, this is unfortunate as that
        # means that when nova is uninstalled it may have just left the
        # host machine in a un-useable state...
        #
        # TODO(harlowja) file a bug to get that fixed...

        def line_matcher(line, start_text):
            if not line:
                return False
            if not line.startswith(start_text):
                return False
            if line.lower().find("nova") == -1:
                return False
            return True

        def translate_rule(line, start_search, start_replace):
            line = re.sub(r"-c\s+[0-9]*\s+[0-9]*", "", line, re.I)
            if not line.startswith(start_search):
                return line
            return line.replace(start_search, start_replace, 1)

        # Isolate the nova rules
        clean_rules = []
        list_cmd = ['iptables', '--list-rules', '--verbose']
        (stdout, _stderr) = sh.execute(list_cmd)
        for line in stdout.splitlines():
            line = line.strip()
            if not line_matcher(line, "-A"):
                continue
            # Translate it into a delete rule operation
            rule = translate_rule(line, "-A", "-D")
            if rule:
                clean_rules.append(rule)

        # Isolate the nova nat rules
        clean_nats = []
        nat_cmd = ['iptables', '--list-rules', '--verbose', '--table', 'nat']
        (stdout, _stderr) = sh.execute(nat_cmd)
        for line in stdout.splitlines():
            line = line.strip()
            if not line_matcher(line, "-A"):
                continue
            # Translate it into a delete rule operation
            rule = translate_rule(line, "-A", "-D")
            if rule:
                clean_nats.append(rule)

        # Isolate the nova chains
        clean_chains = []
        chain_cmd = ['iptables', '--list-rules', '--verbose']
        (stdout, _stderr) = sh.execute(chain_cmd)
        for line in stdout.splitlines():
            if not line_matcher(line, "-N"):
                continue
            # Translate it into a delete rule operation
            rule = translate_rule(line, "-N", "-X")
            if rule:
                clean_chains.append(rule)

        # Isolate the nova nat chains
        clean_nat_chains = []
        nat_chain_cmd = ['iptables', '--list-rules', '--verbose', '--table', 'nat']
        (stdout, _stderr) = sh.execute(nat_chain_cmd)
        for line in stdout.splitlines():
            if not line_matcher(line, "-N"):
                continue
            # Translate it into a delete rule operation
            rule = translate_rule(line, "-N", "-X")
            if rule:
                clean_nat_chains.append(rule)

        # Now execute them...
        for r in clean_rules + clean_chains:
            pieces = r.split(None)
            pieces = ['iptables'] + pieces
            sh.execute(pieces, shell=True)
        for r in clean_nats + clean_nat_chains:
            pieces = r.split(None)
            pieces = ['iptables', '--table', 'nat'] + pieces
            sh.execute(pieces, shell=True)

    def clean(self):
        self._stop_dnsmasq()
        self._clean_iptables()
