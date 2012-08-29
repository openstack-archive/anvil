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

import glob
import re

from anvil import colorizer
from anvil import log as logging
from anvil import shell as sh
from anvil import utils
                                             
from anvil.components import db
from anvil.components import horizon
from anvil.components import nova
from anvil.components import rabbit

from anvil.packaging import yum

from anvil.components.helpers import nova as nhelper

LOG = logging.getLogger(__name__)

# See: http://wiki.libvirt.org/page/SSHPolicyKitSetup
# FIXME(harlowja) take from distro config??
LIBVIRT_POLICY_FN = "/etc/polkit-1/localauthority/50-local.d/50-libvirt-access.pkla"
LIBVIRT_POLICY_CONTENTS = """
[libvirt Management Access]
Identity=${idents}
Action=org.libvirt.unix.manage
ResultAny=yes
ResultInactive=yes
ResultActive=yes
"""
DEF_IDENT = 'unix-group:libvirtd'


class DBInstaller(db.DBInstaller):

    MYSQL_CONF = '/etc/my.cnf'

    def _configure_db_confs(self):
        LOG.info("Fixing up %s mysql configs.", colorizer.quote(self.distro.name))
        new_lines = []
        for line in sh.load_file(DBInstaller.MYSQL_CONF).splitlines():
            if line.startswith('skip-grant-tables'):
                new_lines.append('#' + line)
            elif line.startswith('bind-address'):
                new_lines.append('#' + line)
                new_lines.append('bind-address = 0.0.0.0')
            else:
                new_lines.append(line)
        with sh.Rooted(True):
            sh.write_file_and_backup(DBInstaller.MYSQL_CONF, utils.joinlinesep(*new_lines))


class HorizonInstaller(horizon.HorizonInstaller):

    HTTPD_CONF = '/etc/httpd/conf/httpd.conf'

    def _config_fix_httpd(self):
        LOG.info("Fixing up: %s", colorizer.quote(HorizonInstaller.HTTPD_CONF))
        (user, group) = self._get_apache_user_group()
        new_lines = []
        for line in sh.load_file(HorizonInstaller.HTTPD_CONF).splitlines():
            # Directives in the configuration files are case-insensitive,
            # but arguments to directives are often case sensitive...
            # NOTE(harlowja): we aren't handling multi-line fixups...
            if re.match("^\s*User\s+(.*)$", line, re.I):
                line = "User %s" % (user)
            if re.match("^\s*Group\s+(.*)$", line, re.I):
                line = "Group %s" % (group)
            if re.match("^\s*Listen\s+(.*)$", line, re.I):
                line = "Listen 0.0.0.0:80"
            new_lines.append(line)
        with sh.Rooted(True):
            sh.write_file_and_backup(HorizonInstaller.HTTPD_CONF, utils.joinlinesep(*new_lines))

    def _config_fixups(self):
        self._config_fix_httpd()

    def post_install(self):
        horizon.HorizonInstaller.post_install(self)
        self._config_fixups()

    @property
    def symlinks(self):
        links = super(HorizonInstaller, self).symlinks
        apache_conf_tgt = self.target_config(horizon.HORIZON_APACHE_CONF)
        if apache_conf_tgt not in links:
            links[apache_conf_tgt] = []
        links[apache_conf_tgt].append(sh.joinpths('/etc/',
                                                  self.distro.get_command_config('apache', 'name'),
                                                  'conf.d', horizon.HORIZON_APACHE_CONF))
        return links


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
            with sh.Rooted(True):
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


class NovaInstaller(nova.NovaInstaller):

    def _get_policy(self, ident_users):
        return utils.expand_template(LIBVIRT_POLICY_CONTENTS,
                                     params={
                                         'idents': (";".join(ident_users)),
                                     })

    def _get_policy_users(self):
        ident_users = [
            DEF_IDENT,
            'unix-user:%s' % (sh.getuser()),
        ]
        return ident_users

    def configure(self):
        configs_made = nova.NovaInstaller.configure(self)
        driver_canon = nhelper.canon_virt_driver(self.get_option('virt_driver'))
        if driver_canon == 'libvirt':
            # Create a libvirtd user group
            if not sh.group_exists('libvirtd'):
                cmd = ['groupadd', 'libvirtd']
                sh.execute(*cmd, run_as_root=True)
            if not sh.isfile(LIBVIRT_POLICY_FN):
                contents =  self._get_policy(self._get_policy_users())
                with sh.Rooted(True):
                    sh.mkdirslist(sh.dirname(LIBVIRT_POLICY_FN))
                    sh.write_file(LIBVIRT_POLICY_FN, contents)
                configs_made += 1
        return configs_made


class YumPackagerWithRelinks(yum.YumPackager):

    def _remove(self, pkg):
        yum.YumPackager._remove(self, pkg)
        options = pkg.get('packager_options') or {}
        links = options.get('links') or []
        for entry in links:
            if sh.islink(entry['target']):
                sh.unlink(entry['target'])

    def _install(self, pkg):
        yum.YumPackager._install(self, pkg)
        options = pkg.get('packager_options') or {}
        links = options.get('links') or []
        for entry in links:
            tgt = entry.get('target')
            src = entry.get('source')
            if not tgt or not src:
                continue
            src = glob.glob(src)
            if not isinstance(tgt, (list, tuple)):
                tgt = [tgt]
            if len(src) != len(tgt):
                raise RuntimeError("Unable to link %s sources to %s locations" % (len(src), len(tgt)))
            for i in range(len(src)):
                i_src = src[i]
                i_tgt = tgt[i]
                if not sh.islink(i_tgt):
                    sh.symlink(i_src, i_tgt)
