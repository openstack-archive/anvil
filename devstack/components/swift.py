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
from devstack import log as logging
from devstack import settings
from devstack import shell as sh

# id
TYPE = settings.SWIFT
LOG = logging.getLogger("devstack.components.swift")

#swift has alot of config files!
SWIFT_CONF = 'swift.conf'
PROXY_SERVER_CONF = 'proxy-server.conf'
ACCOUNT_SERVER_CONF = 'account-server.conf'
CONTAINER_SERVER_CONF = 'container-server.conf'
OBJECT_SERVER_CONF = 'object-server.conf'
RSYNC_CONF = 'rsyncd.conf'
SYSLOG_CONF = 'rsyslog.conf'
SWIFT_MAKERINGS = 'swift-remakerings'
SWIFT_STARTMAIN = 'swift-startmain'
SWIFT_INIT = 'swift-init'
SWIFT_IMG = 'drives/images/swift.img'
DEVICE_PATH = 'drives/sdb1'
CONFIGS = [SWIFT_CONF, PROXY_SERVER_CONF, ACCOUNT_SERVER_CONF,
           CONTAINER_SERVER_CONF, OBJECT_SERVER_CONF, RSYNC_CONF,
           SYSLOG_CONF, SWIFT_MAKERINGS, SWIFT_STARTMAIN]

# subdirs of the git checkout
BIN_DIR = 'bin'
CONFIG_DIR = 'etc'

# what to start
APP_OPTIONS = {
}

#the pkg json files swift requires for installation
REQ_PKGS = ['general.json', 'swift.json']


class SwiftUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)
        self.datadir = sh.joinpths(self.appdir, self.cfg.get('swift', 'data_location'))

    def pre_uninstall(self):
        sh.umount(sh.joinpths(self.datadir, DEVICE_PATH))
        sh.replace_in_file('/etc/default/rsync',
                           'RSYNC_ENABLE=true',
                           'RSYNC_ENABLE=false',
                           run_as_root=True)

    def post_uninstall(self):
        sh.execute('restart', 'rsyslog', run_as_root=True)
        sh.execute('/etc/init.d/rsync', 'restart', run_as_root=True)


class SwiftInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)
        self.datadir = sh.joinpths(self.appdir, self.cfg.get('swift', 'data_location'))
        self.logdir = sh.joinpths(self.datadir, 'logs')
        self.startmain_file = sh.joinpths(self.bindir, SWIFT_STARTMAIN)
        self.makerings_file = sh.joinpths(self.bindir, SWIFT_MAKERINGS)
        self.fs_dev = sh.joinpths(self.datadir, DEVICE_PATH)
        self.fs_image = sh.joinpths(self.datadir, SWIFT_IMG)
        self.auth_server = 'keystone'

    def _get_download_locations(self):
        places = list()
        places.append({
                'uri': ('git', 'swift_repo'),
                'branch': ('git', 'swift_branch')
            })
        return places

    def _get_config_files(self):
        return list(CONFIGS)

    def _get_pkgs(self):
        return list(REQ_PKGS)

    def _get_symlinks(self):
        links = dict()
        for fn in self._get_config_files():
            source_fn = self._get_target_config_name(fn)
            links[source_fn] = sh.joinpths("/", "etc", "swift", fn)
        return links

    def warm_configs(self):
        pws = ['service_token', 'swift_hash']
        for pw_key in pws:
            self.cfg.get("passwords", pw_key)

    def _get_param_map(self, config_fn):
        return {
            'USER': self.cfg.get('swift', 'swift_user'),
            'GROUP': self.cfg.get('swift', 'swift_group'),
            'SWIFT_DATA_LOCATION': self.datadir,
            'SWIFT_CONFIG_LOCATION': self.cfgdir,
            'SERVICE_TOKEN': self.cfg.get('passwords', 'service_token'),
            'AUTH_SERVER': self.auth_server,
            'SWIFT_HASH': self.cfg.get('passwords', 'swift_hash'),
            'SWIFT_LOGDIR': self.logdir,
            'SWIFT_PARTITION_POWER_SIZE': self.cfg.get('swift',
                                                       'partition_power_size'),
            'NODE_PATH': '%NODE_PATH%',
            'BIND_PORT': '%BIND_PORT%',
            'LOG_FACILITY': '%LOG_FACILITY%'
            }

    def __create_data_location(self):
        sh.create_loopback_file(fname=self.fs_image,
                                size=int(self.cfg.get('swift',
                                                  'loopback_disk_size')),
                                fs_type='xfs')
        self.tracewriter.file_touched(self.fs_image)
        sh.mount_loopback_file(self.fs_image, self.fs_dev, 'xfs')
        sh.chown_r(self.fs_dev, sh.geteuid(), sh.getegid())

    def __create_node_config(self, node_number, port):
        for type_ in ['object', 'container', 'account']:
            sh.copy_replace_file(sh.joinpths(self.cfgdir, '%s-server.conf' % type_),
                                 sh.joinpths(self.cfgdir, '%s-server/%d.conf' \
                                                 % (type_, node_number)),
                                 {
                                  '%NODE_PATH%': sh.joinpths(self.datadir, str(node_number)),
                                  '%BIND_PORT%': str(port),
                                  '%LOG_FACILITY%': str(2 + node_number)
                                 })
            port += 1

    def __delete_templates(self):
        for type_ in ['object', 'container', 'account']:
            sh.unlink(sh.joinpths(self.cfgdir, '%s-server.conf' % type_))

    def __create_nodes(self):
        for i in range(1, 5):
            self.tracewriter.make_dir(sh.joinpths(self.fs_dev,
                                                    '%d/node' % i))
            self.tracewriter.symlink(sh.joinpths(self.fs_dev, str(i)),
                                     sh.joinpths(self.datadir, str(i)))
            self.__create_node_config(i, 6010 + (i - 1) * 5)
        self.__delete_templates()

    def __turn_on_rsync(self):
        self.tracewriter.symlink(sh.joinpths(self.cfgdir, RSYNC_CONF),
                                 '/etc/rsyncd.conf')
        sh.replace_in_file('/etc/default/rsync',
                           'RSYNC_ENABLE=false',
                           'RSYNC_ENABLE=true',
                           run_as_root=True)

    def __create_log_dirs(self):
        self.tracewriter.make_dir(sh.joinpths(self.logdir, 'hourly'))
        self.tracewriter.symlink(sh.joinpths(self.cfgdir, SYSLOG_CONF),
                                 '/etc/rsyslog.d/10-swift.conf')

    def __setup_binaries(self):
        sh.move(sh.joinpths(self.cfgdir, SWIFT_MAKERINGS),
                self.makerings_file)
        sh.chmod(self.makerings_file, 777)
        self.tracewriter.file_touched(self.makerings_file)

        sh.move(sh.joinpths(self.cfgdir, SWIFT_STARTMAIN),
                self.startmain_file)
        sh.chmod(self.startmain_file, 777)
        self.tracewriter.file_touched(self.startmain_file)

    def __make_rings(self):
        sh.execute(self.makerings_file, run_as_root=True)

    def post_install(self):
        self.__create_data_location()
        self.__create_nodes()
        self.__turn_on_rsync()
        self.__create_log_dirs()
        self.__setup_binaries()
        self.__make_rings()


class SwiftRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, TYPE, *args, **kargs)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)

    def start(self):
        sh.execute('restart', 'rsyslog', run_as_root=True)
        sh.execute('/etc/init.d/rsync', 'restart', run_as_root=True)
        sh.execute(sh.joinpths(self.bindir, SWIFT_INIT), 'all', 'start',
                   run_as_root=True)

    def stop(self):
        sh.execute(sh.joinpths(self.bindir, SWIFT_INIT), 'all', 'stop',
                   run_as_root=True)

    def restart(self):
        sh.execute(sh.joinpths(self.bindir, SWIFT_INIT), 'all', 'restart',
                   run_as_root=True)
