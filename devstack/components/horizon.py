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

from devstack import component as comp
from devstack import exceptions as excp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

#id
TYPE = settings.HORIZON
LOG = logging.getLogger("devstack.components.horizon")

#actual dir names
ROOT_HORIZON = 'horizon'
ROOT_DASH = 'openstack_dashboard'

#name used for python install trace
HORIZON_NAME = ROOT_HORIZON
DASH_NAME = 'dashboard'

#config files messed with
HORIZON_PY_CONF = "horizon_settings.py"
HORIZON_PY_CONF_TGT = ['local', 'local_settings.py']
HORIZON_APACHE_CONF = '000-default'
CONFIGS = [HORIZON_PY_CONF, HORIZON_APACHE_CONF]

#http://wiki.apache.org/httpd/DistrosDefaultLayout

#db sync that needs to happen for horizon
DB_SYNC_CMD = ['python', 'manage.py', 'syncdb']

#special apache directory (TODO describe more about this)
BLACKHOLE_DIR = '.blackhole'

APACHE_ERROR_LOG_FN = "error.log"
APACHE_ACCESS_LOG_FN = "access.log"
APACHE_DEF_PORT = 80

#TODO: maybe this should be a subclass that handles these differences
APACHE_FIXUPS = {
    'SOCKET_CONF': "/etc/httpd/conf.d/wsgi-socket-prefix.conf",
    'HTTPD_CONF': '/etc/httpd/conf/httpd.conf',
}
APACHE_FIXUPS_DISTROS = [settings.RHEL6, settings.FEDORA16]

#for when quantum client is not need we need some fake files so python doesn't croak
FAKE_QUANTUM_FILES = ['__init__.py', 'client.py']

#users which apache may not like starting as
BAD_APACHE_USERS = ['root']

#apache logs will go here
LOGS_DIR = "logs"

#pip files that horizon requires
REQ_PIPS = ['general.json', 'horizon.json']


class HorizonUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)


class HorizonInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)
        self.horizon_dir = sh.joinpths(self.appdir, ROOT_HORIZON)
        self.dash_dir = sh.joinpths(self.appdir, ROOT_DASH)
        self.log_dir = sh.joinpths(self.component_root, LOGS_DIR)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "horizon_repo"),
            'branch': ("git", "horizon_branch"),
        })
        return places

    def verify(self):
        self._check_ug()

    def _get_symlinks(self):
        links = comp.PythonInstallComponent._get_symlinks(self)
        src = self._get_target_config_name(HORIZON_APACHE_CONF)
        links[src] = self.distro.commands['apache']['settings']['conf-link-target']
        if utils.service_enabled(settings.QUANTUM_CLIENT, self.instances, False):
            #TODO remove this junk, blah, puke that we have to do this
            qc = self.instances[settings.QUANTUM_CLIENT]
            src_pth = sh.joinpths(qc.appdir, 'quantum')
            tgt_dir = sh.joinpths(self.dash_dir, 'quantum')
            links[src_pth] = tgt_dir
        return links

    def _check_ug(self):
        (user, group) = self._get_apache_user_group()
        if not sh.user_exists(user):
            msg = "No user named %s exists on this system!" % (user)
            raise excp.ConfigException(msg)
        if not sh.group_exists(group):
            msg = "No group named %s exists on this system!" % (group)
            raise excp.ConfigException(msg)
        if user in BAD_APACHE_USERS:
            msg = "You may want to adjust your configuration, (user=%s, group=%s) will not work with apache!" % (user, group)
            raise excp.ConfigException(msg)

    def _get_pips(self):
        return list(REQ_PIPS)

    def _get_target_config_name(self, config_name):
        if config_name == HORIZON_PY_CONF:
            return sh.joinpths(self.dash_dir, *HORIZON_PY_CONF_TGT)
        else:
            return comp.PythonInstallComponent._get_target_config_name(self, config_name)

    def _get_config_files(self):
        return list(CONFIGS)

    def _setup_blackhole(self):
        #create an empty directory that apache uses as docroot
        self.tracewriter.dirs_made(*sh.mkdirslist(sh.joinpths(self.appdir, BLACKHOLE_DIR)))

    def _sync_db(self):
        #Initialize the horizon database (it stores sessions and notices shown to users).
        #The user system is external (keystone).
        LOG.info("Initializing the horizon database.")
        sh.execute(*DB_SYNC_CMD, cwd=self.appdir)

    def _ensure_db_access(self):
        # ../openstack-dashboard/local needs to be writeable by the runtime user
        # since currently its storing the sql-lite databases there (TODO fix that)
        path = sh.joinpths(self.dash_dir, 'local')
        if sh.isdir(path):
            (user, group) = self._get_apache_user_group()
            LOG.debug("Changing ownership (recursively) of %s so that it can be used by %s - %s",
                            path, user, group)
            uid = sh.getuid(user)
            gid = sh.getgid(group)
            sh.chown_r(path, uid, gid)

    def pre_install(self):
        comp.PythonInstallComponent.pre_install(self)
        self.tracewriter.dirs_made(*sh.mkdirslist(self.log_dir))

    def _config_fixups(self):
        #currently just handling rhel fixups
        #TODO: maybe this should be a subclass that handles these differences
        if not (self.distro in APACHE_FIXUPS_DISTROS):
            return
        #it seems like to get this to work
        #we need to do some conf.d/conf work which sort of sucks
        (user, group) = self._get_apache_user_group()
        socket_fn = APACHE_FIXUPS.get("SOCKET_CONF")
        self.tracewriter.file_touched(socket_fn)
        #not recorded since we aren't really creating this
        httpd_fn = APACHE_FIXUPS.get("HTTPD_CONF")
        with sh.Rooted(True):
            #fix the socket prefix to someplace we can use
            fc = "WSGISocketPrefix %s" % (sh.joinpths(self.log_dir, "wsgi-socket"))
            sh.write_file(socket_fn, fc)
            #now adjust the run user and group (of httpd.conf)
            new_lines = list()
            for line in sh.load_file(httpd_fn).splitlines():
                if line.startswith("User "):
                    line = "User %s" % (user)
                if line.startswith("Group "):
                    line = "Group %s" % (group)
                new_lines.append(line)
            sh.write_file(httpd_fn, utils.joinlinesep(*new_lines))

    def _fix_quantum(self):
        if not (utils.service_enabled(settings.QUANTUM_CLIENT, self.instances, False)):
            #make the fake quantum (apparently needed so imports don't fail???)
            #TODO remove this...
            quantum_dir = sh.joinpths(self.dash_dir, 'quantum')
            if not sh.isdir(quantum_dir):
                self.tracewriter.dirs_made(*sh.mkdirslist(quantum_dir))
                for fn in FAKE_QUANTUM_FILES:
                    self.tracewriter.file_touched(sh.touch_file(sh.joinpths(quantum_dir, fn)))

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        self._fix_quantum()
        self._sync_db()
        self._setup_blackhole()
        self._ensure_db_access()
        self._config_fixups()

    def _get_apache_user_group(self):
        user = self.cfg.getdefaulted('horizon', 'apache_user', sh.getuser())
        group = self.cfg.getdefaulted('horizon', 'apache_group', sh.getgroupname())
        return (user, group)

    def _get_param_map(self, config_fn):
        #this dict will be used to fill in the configuration
        #params with actual values
        mp = dict()
        if config_fn == HORIZON_APACHE_CONF:
            (user, group) = self._get_apache_user_group()
            mp['ACCESS_LOG'] = sh.joinpths(self.log_dir, APACHE_ACCESS_LOG_FN)
            mp['ERROR_LOG'] = sh.joinpths(self.log_dir, APACHE_ERROR_LOG_FN)
            mp['GROUP'] = group
            mp['HORIZON_DIR'] = self.appdir
            mp['HORIZON_PORT'] = self.cfg.getdefaulted('horizon', 'port', APACHE_DEF_PORT)
            mp['USER'] = user
            mp['VPN_DIR'] = sh.joinpths(self.appdir, "vpn")
        else:
            mp['OPENSTACK_HOST'] = self.cfg.get('host', 'ip')
        return mp


class HorizonRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, *args, **kargs)

    def start(self):
        curr_status = self.status()
        if curr_status == comp.STATUS_STARTED:
            return self.restart()
        else:
            cmds = [{
                    'cmd': self.distro.commands['apache']['start'],
                    'run_as_root': True,
                    }]
            utils.execute_template(*cmds,
                    check_exit_code=True,
                    params={})
            return 1

    def restart(self):
        cmds = [{
            'cmd': self.distro.commands['apache']['restart'],
            'run_as_root': True,
            }]
        utils.execute_template(*cmds,
                                check_exit_code=True,
                                params={})
        return 1

    def stop(self):
        curr_status = self.status()
        if curr_status != comp.STATUS_STOPPED:
            cmds = [{
                    'cmd': self.distro.commands['apache']['stop'],
                    'run_as_root': True,
                    }]
            utils.execute_template(*cmds,
                                    check_exit_code=True,
                                    params={})
            return 1
        return 0

    def status(self):
        cmds = [{
                'cmd': self.distro.commands['apache']['status'],
                'run_as_root': True,
                }]
        run_result = utils.execute_template(*cmds,
                                             check_exit_code=False,
                                             params={})
        if not run_result or not run_result[0]:
            return comp.STATUS_UNKNOWN
        (sysout, stderr) = run_result[0]
        combined = str(sysout) + str(stderr)
        combined = combined.lower()
        if sysout.find("is running") != -1:
            return comp.STATUS_STARTED
        elif sysout.find("not running") != -1 or sysout.find("stopped") != -1:
            return comp.STATUS_STOPPED
        else:
            return comp.STATUS_UNKNOWN
