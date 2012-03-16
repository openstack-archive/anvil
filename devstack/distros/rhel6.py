# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#    Copyright (C) 2012 Dreamhost Inc. All Rights Reserved.
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

"""Platform-specific logic for RHEL6 components.
"""

from devstack.components import db
from devstack import log as logging

LOG = logging.getLogger(__name__)


class Rhel6DBInstaller(db.DBInstaller):

    def _configure_db_confs(self):
        dbtype = self.cfg.get("db", "type")
        if dbtype == 'mysql':
            LOG.info("Fixing up mysql configs.")
            fc = sh.load_file('/etc/my.cnf')
            lines = fc.splitlines()
            new_lines = list()
            for line in lines:
                if line.startswith('skip-grant-tables'):
                    line = '#' + line
                new_lines.append(line)
            fc = utils.joinlinesep(*new_lines)
            with sh.Rooted(True):
                sh.write_file('/etc/my.cnf', fc)
