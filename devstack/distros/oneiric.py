# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#    Copyright (C) 2012 New Dream Network, LLC (DreamHost) All Rights Reserved.
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

"""Platform-specific logic for Ubunutu Oneiric components.
"""

import tempfile
import time

from devstack.components import db
from devstack import log as logging
from devstack import shell as sh
from devstack import utils
from devstack.packaging import apt

LOG = logging.getLogger(__name__)


class DBInstaller(db.DBInstaller):

    def _configure_db_confs(self):
        LOG.info("Fixing up %s mysql configs.", self.distro.name)
        fc = sh.load_file('/etc/mysql/my.cnf')
        lines = fc.splitlines()
        new_lines = list()
        for line in lines:
            if line.startswith('bind-address'):
                line = 'bind-address = %s' % ('0.0.0.0')
            new_lines.append(line)
        fc = utils.joinlinesep(*new_lines)
        with sh.Rooted(True):
            sh.write_file('/etc/mysql/my.cnf', fc)


class RabbitPackager(apt.AptPackager):

    def _remove(self, pkg):
        #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878597
        #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878600
        name = pkg['name']
        LOG.debug("Handling special remove of %s." % (name))
        pkg_full = self._format_pkg_name(name, pkg.get("version"))
        cmd = apt.APT_REMOVE + [pkg_full]
        self._execute_apt(cmd)
        #probably useful to do this
        time.sleep(1)
        #purge
        cmd = apt.APT_PURGE + [pkg_full]
        self._execute_apt(cmd)
        return True

    def install(self, pkg):
        #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878597
        #https://bugs.launchpad.net/ubuntu/+source/rabbitmq-server/+bug/878600
        name = pkg['name']
        LOG.debug("Handling special install of %s." % (name))
        #this seems to be a temporary fix for that bug
        with tempfile.TemporaryFile() as f:
            pkg_full = self._format_pkg_name(name, pkg.get("version"))
            cmd = apt.APT_INSTALL + [pkg_full]
            self._execute_apt(cmd, stdout_fh=f, stderr_fh=f)
