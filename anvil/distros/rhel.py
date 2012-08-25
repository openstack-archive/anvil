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

import contextlib
import glob
import os
import re
import shutil

from Cheetah.Template import Template

from anvil import colorizer
from anvil import component as comp
from anvil import log as logging
from anvil import packager as pack
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
Identity={idents}
Action=org.libvirt.unix.manage
ResultAny=yes
ResultInactive=yes
ResultActive=yes
"""
DEF_IDENT = 'unix-group:libvirtd'


class DBInstaller(db.DBInstaller):

    def _configure_db_confs(self):
        LOG.info("Fixing up %s mysql configs.", colorizer.quote(self.distro.name))
        fc = sh.load_file('/etc/my.cnf')
        lines = fc.splitlines()
        new_lines = []
        for line in lines:
            if line.startswith('skip-grant-tables'):
                line = '#' + line
            new_lines.append(line)
        fc = utils.joinlinesep(*new_lines)
        with sh.Rooted(True):
            sh.write_file('/etc/my.cnf', fc)


class HorizonInstaller(horizon.HorizonInstaller):

    def _config_fix_wsgi(self):
        # This is recorded so it gets cleaned up during uninstall
        self.tracewriter.file_touched("/etc/httpd/conf.d/wsgi-socket-prefix.conf")
        LOG.info("Fixing up: %s", colorizer.quote("/etc/httpd/conf.d/wsgi-socket-prefix.conf"))
        contents = "WSGISocketPrefix %s" % (sh.joinpths(self.log_dir, "wsgi-socket"))
        with sh.Rooted(True):
            # The name seems to need to come after wsgi.conf (so thats what we are doing)
            sh.write_file("/etc/httpd/conf.d/wsgi-socket-prefix.conf", contents)

    def _config_fix_httpd(self):
        LOG.info("Fixing up: %s", colorizer.quote('/etc/httpd/conf/httpd.conf'))
        (user, group) = self._get_apache_user_group()
        old_lines = sh.load_file('/etc/httpd/conf/httpd.conf').splitlines()
        new_lines = list()
        for line in old_lines:
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
        contents = utils.joinlinesep(*new_lines)
        with sh.Rooted(True):
            sh.write_file('/etc/httpd/conf/httpd.conf', contents)

    def _config_fixups(self):
        self._config_fix_wsgi()
        self._config_fix_httpd()


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
        base_dir = sh.joinpths("/", 'var', 'log', 'rabbitmq')
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
        return LIBVIRT_POLICY_CONTENTS.format(idents=(";".join(ident_users)))

    def _get_policy_users(self):
        ident_users = set()
        ident_users.add(DEF_IDENT)
        ident_users.add('unix-user:%s' % (sh.getuser()))
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
        response = yum.YumPackager._remove(self, pkg)
        if response:
            options = pkg.get('packager_options') or {}
            links = options.get('links') or []
            for entry in links:
                if sh.islink(entry['target']):
                    sh.unlink(entry['target'])
        return response

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
            tgt = glob.glob(tgt)
            if len(src) != len(tgt):
                raise RuntimeError("Unable to link %s sources to %s locations" % (len(src), len(tgt)))
            for i in range(len(src)):
                i_src = src[i]
                i_tgt = tgt[i]
                if not sh.islink(i_tgt):
                    sh.symlink(i_src, i_tgt)
        return True


class DependencyPackager(comp.Component):
    def __init__(self, *args, **kargs):
        comp.Component.__init__(self, *args, **kargs)
        self.package_dir = sh.joinpths(self.get_option('component_dir'), 'package')
        self.build_paths = {}
        for name in ['SOURCES', 'SPECS', 'SRPMS', 'RPMS', 'BUILD']:
            # Remove any old packaging directories...
            sh.deldir(sh.joinpths(self.package_dir, name), True)
            self.build_paths[name] = sh.mkdir(sh.joinpths(self.package_dir, name))

    def _requirements(self):
        return {
            'install': self._install_requirements(),
            'build': self._build_requirements(),
        }

    @property
    def details(self):
        return {
            'summary': 'Package build of %s on %s' % (self.name, utils.rcf8222date()),
            'name': self.name,
            'version': 0,
            'release': 1,
            'packager': "%s <%s@%s>" % (sh.getuser(), sh.getuser(), sh.hostname()),
            'description': '',
            'changelog': '',
            'license': 'Apache License, Version 2.0',
        }

    def _build_details(self):
        return {
            'arch': 'noarch',
        }

    def _gather_files(self):
        source_fn = self._make_source_archive()
        sources = []
        if source_fn:
            sources.append(source_fn)
        return {
            'sources': sources,
            'files': [],
            'directories': [],
            'docs': [],
        }

    def _defines(self):
        define_what = []
        define_what.append("_topdir %s" % (self.package_dir))
        return define_what

    def _make_source_archive(self):
        return None

    def _make_fn(self, ext):
        your_fn = "%s-%s-%s.%s" % (self.details['name'], 
                                   self.details['version'],
                                   self.details['release'], ext)
        return your_fn

    def _create_package(self):
        params = {
            'files': self._gather_files(),
            'requires': self._requirements(),
            'defines': self._defines(),
            'build': self._build_details(),
            'who': sh.getuser(),
            'date': utils.rcf8222date(),
            'details': self.details,
        }
        (_fn, content) = utils.load_template('packaging', 'spec.tmpl')
        spec_fn = sh.joinpths(self.build_paths['SPECS'], self._make_fn("spec"))
        LOG.debug("Creating spec file %s with params:", spec_fn)
        utils.log_object(params, logger=LOG, level=logging.DEBUG)
        sh.write_file(spec_fn, Template(content, searchList=[params]).respond())

    def _build_requirements(self):
        return []

    def _install_requirements(self):
        i_sibling = self.siblings.get('install')
        if not i_sibling:
            return []
        requirements = []
        for p in i_sibling.packages:
            if 'version' in p:
                if pack.contains_version_check(p['version']):
                    # This seems to mean only this version...
                    real_version = p['version'].replace('==', '=')
                    requirements.append("%s %s" % (p['name'], real_version))
                else:
                    requirements.append("%s = %s" % (p['name'], p['version']))
            else:
                requirements.append("%s" % (p['name']))
        return requirements

    def package(self):
        self._create_package()
        return self.package_dir 


class PythonPackager(DependencyPackager):
    def _build_requirements(self):
        return [
            'python',
            'python-devel',
            'gcc',
            'python-setuptools',
        ]
    
