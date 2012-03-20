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
from devstack.components import nova

from devstack.packaging import yum

LOG = logging.getLogger(__name__)

SOCKET_CONF = "/etc/httpd/conf.d/wsgi-socket-prefix.conf"
HTTPD_CONF = '/etc/httpd/conf/httpd.conf'

# Need to relink for rhel (not a bug!)
RHEL_RELINKS = {
    'python-webob1.0': (
        '/usr/lib/python2.6/site-packages/WebOb-1.0.8-py2.6.egg/webob/',
        '/usr/lib/python2.6/site-packages/webob'
    ),
    'python-nose1.1': (
        '/usr/lib/python2.6/site-packages/nose-1.1.2-py2.6.egg/nose/',
        '/usr/lib/python2.6/site-packages/nose',
    )
}

# See: http://wiki.libvirt.org/page/SSHPolicyKitSetup
# FIXME: take from distro config??
LIBVIRT_POLICY_FN = "/etc/polkit-1/localauthority/50-local.d/50-libvirt-access.pkla"
LIBVIRT_POLICY_CONTENTS = """
[libvirt Management Access]
Identity={idents}
Action=org.libvirt.unix.manage
ResultAny=yes
ResultInactive=yes
ResultActive=yes
"""
DEF_IDENT = 'unix-group:libvirtd'


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


class NovaInstaller(nova.NovaInstaller):

    def configure(self):
        configs_made = nova.NovaInstaller.configure(self)
        driver_canon = nova.canon_virt_driver(self.cfg.get('nova', 'virt_driver'))
        if driver_canon == 'libvirt':
            ident_users = set()
            ident_users.add(DEF_IDENT)
            ident_users.add('unix-user:%s' % (sh.getuser()))
            fc_contents = LIBVIRT_POLICY_CONTENTS.format(idents=(";".join(ident_users)))
            with sh.Rooted(True):
                dirs_made = sh.mkdirslist(sh.dirname(LIBVIRT_POLICY_FN))
                sh.write_file(LIBVIRT_POLICY_FN, fc_contents)
            self.tracewriter.cfg_file_written(LIBVIRT_POLICY_FN)
            self.tracewriter.dirs_made(*dirs_made)
            configs_made += 1
        return configs_made


class YumPackager(yum.YumPackager):

    def _remove_special(self, name, info):
        if name in RHEL_RELINKS:
            # Note: we don't return true here so that
            # the normal package cleanup happens...
            (_, tgt) = RHEL_RELINKS.get(name)
            if sh.islink(tgt):
                sh.unlink(tgt)
        return False

    def _install_special(self, name, info):
        if name in RHEL_RELINKS:
            full_pkg_name = self._format_pkg_name(name, info.get("version"))
            install_cmd = yum.YUM_INSTALL + [full_pkg_name]
            self._execute_yum(install_cmd)
            (src, tgt) = RHEL_RELINKS.get(name)
            if not sh.islink(tgt):
                # This is actually a feature, EPEL must not conflict with RHEL, so X pkg installs newer version in parallel.
                #
                # This of course doesn't work when running from git like devstack does....
                sh.symlink(src, tgt)
            return True
        else:
            return False
