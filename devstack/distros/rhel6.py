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

"""Platform-specific logic for RedHat Enterprise Linux v6 components.
"""

from devstack import log as logging
from devstack import shell as sh
from devstack import utils

from devstack.components import db
from devstack.components import horizon

from devstack.packaging import yum

LOG = logging.getLogger(__name__)

SOCKET_CONF = "/etc/httpd/conf.d/wsgi-socket-prefix.conf"
HTTPD_CONF = '/etc/httpd/conf/httpd.conf'

# Need to relink for rhel (not a bug!)
RHEL_RELINKS = {
    'python-webob1.0': {
        "src": '/usr/lib/python2.6/site-packages/WebOb-1.0.8-py2.6.egg/webob/',
        'tgt': '/usr/lib/python2.6/site-packages/webob',
    },
    'python-nose1.1': {
        "src": '/usr/lib/python2.6/site-packages/nose-1.1.2-py2.6.egg/nose/',
        'tgt': '/usr/lib/python2.6/site-packages/nose',
    },
}


class DBInstaller(db.DBInstaller):

    def _configure_db_confs(self):
        LOG.info("Fixing up %s mysql configs.", self.distro.name)
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


class HorizonInstaller(horizon.HorizonInstaller):

    def _config_fixups(self):
        (user, group) = self._get_apache_user_group()
        # This is recorded so it gets cleaned up during uninstall
        self.tracewriter.file_touched(SOCKET_CONF)
        LOG.info("Fixing up %s and %s files" % (SOCKET_CONF, HTTPD_CONF))
        with sh.Rooted(True):
            # Fix the socket prefix to someplace we can use
            fc = "WSGISocketPrefix %s" % (sh.joinpths(self.log_dir, "wsgi-socket"))
            sh.write_file(SOCKET_CONF, fc)
            # Now adjust the run user and group (of httpd.conf)
            new_lines = list()
            for line in sh.load_file(HTTPD_CONF).splitlines():
                if line.startswith("User "):
                    line = "User %s" % (user)
                if line.startswith("Group "):
                    line = "Group %s" % (group)
                new_lines.append(line)
            sh.write_file(HTTPD_CONF, utils.joinlinesep(*new_lines))


class YumPackager(yum.YumPackager):

    def _remove_special(self, name, info):
        if name in RHEL_RELINKS:
            # Note: we don't return true here so that
            # the normal package cleanup happens...
            sh.unlink(RHEL_RELINKS.get(name).get("tgt"))
        return False

    def _install_special(self, name, info):
        if name in RHEL_RELINKS:
            full_pkg_name = self._format_pkg_name(name, info.get("version"))
            install_cmd = yum.YUM_INSTALL + [full_pkg_name]
            self._execute_yum(install_cmd)
            tgt = RHEL_RELINKS.get(pkgname).get("tgt")
            src = RHEL_RELINKS.get(pkgname).get("src")
            if not sh.islink(tgt):
                # This is actually a feature, EPEL must not conflict with RHEL, so X pkg installs newer version in parallel.
                #
                # This of course doesn't work when running from git like devstack does....
                sh.symlink(src, tgt)
            return True
        else:
            return False
