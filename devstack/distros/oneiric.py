"""Platform-specific logic for Ubunutu Oneiric components.
"""

from devstack.components import db
from devstack import log as logging
from devstack import shell as sh
from devstack import utils

LOG = logging.getLogger(__name__)


class OneiricDBInstaller(db.DBInstaller):

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
