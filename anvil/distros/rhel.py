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

"""
Platform-specific logic for RedHat Enterprise Linux components.
"""

import re

from anvil import cfg
from anvil import colorizer
from anvil import log as logging
from anvil import shell as sh

from anvil.components import db
from anvil.components import rabbit


LOG = logging.getLogger(__name__)


class DBInstaller(db.DBInstaller):

    MYSQL_CONF = '/etc/my.cnf'

    def _configure_db_confs(self):
        LOG.info("Fixing up %s mysql configs.", colorizer.quote(self.distro.name))
        my_cnf = cfg.RewritableConfigParser(fns=[DBInstaller.MYSQL_CONF])
        my_cnf.remove_option('mysqld', 'skip-grant-tables')
        my_cnf.set('mysqld', 'default-storage-engine', 'InnoDB')
        my_cnf.set('mysqld', 'bind-address', '0.0.0.0')
        sh.write_file_and_backup(DBInstaller.MYSQL_CONF, my_cnf.stringify())


class RabbitRuntime(rabbit.RabbitRuntime):

    def _fix_log_dir(self):
        # This seems needed...
        #
        # Due to the following:
        # <<< Restarting rabbitmq-server: RabbitMQ is not running
        # <<< sh: /var/log/rabbitmq/startup_log: Permission denied
        # <<< FAILED - check /var/log/rabbitmq/startup_{log, _err}
        #
        # See: http://lists.rabbitmq.com/pipermail/rabbitmq-discuss/2011-March/011916.html
        # This seems like a bug, since we are just using service init and service restart...
        # And not trying to run this service directly...
        base_dir = sh.joinpths("/var/log", 'rabbitmq')
        if sh.isdir(base_dir):
            # Seems like we need root perms to list that directory...
            for fn in sh.listdir(base_dir):
                if re.match("(.*?)(err|log)$", fn, re.I):
                    sh.chmod(sh.joinpths(base_dir, fn), 0666)

    def start(self):
        self._fix_log_dir()
        return rabbit.RabbitRuntime.start(self)

    def restart(self):
        self._fix_log_dir()
        return rabbit.RabbitRuntime.restart(self)
