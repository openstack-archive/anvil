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

import os
import os.path

from devstack import component as comp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

LOG = logging.getLogger("devstack.components.swift")

# id
TYPE = settings.SWIFT

SWIFT_CONF = 'swift.conf'
PROXY_SERVER_CONF = 'proxy-server.conf'
ACCOUNT_SERVER_CONF = 'account-server.conf'
CONTAINER_SERVER_CONF = 'container-server.conf'
OBJECT_SERVER_CONF = 'object-server.conf'
RSYNC_CONF = 'rsyncd.conf'
SYSLOG_CONF = 'rsyslog.conf'
SWIFT_MAKERINGS = 'swift-remakerings'
SWIFT_STARTMAIN = 'swift-startmain'
CONFIGS = [SWIFT_CONF, PROXY_SERVER_CONF, ACCOUNT_SERVER_CONF,
           CONTAINER_SERVER_CONF, OBJECT_SERVER_CONF, RSYNC_CONF,
           SYSLOG_CONF, SWIFT_MAKERINGS, SWIFT_STARTMAIN]

SWIFT_NAME = 'swift'

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


class SwiftInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)
        self.datadir = sh.joinpths(self.appdir, self.cfg.get('swift', 'data_location'))
        self.logdir = sh.joinpths(self.datadir, 'logs')
        self.auth_server = 'keystone'

    def _get_download_locations(self):
        return comp.PythonInstallComponent._get_download_locations(self) + [
            {
                'uri': ('git', 'swift_repo'),
                'branch': ('git', 'swift_branch')
            }]

    def _get_config_files(self):
        return list(CONFIGS)

    def _get_pkgs(self):
        return list(REQ_PKGS)

    def _get_param_map(self, config_fn):
        return {
            'USER': self.cfg.get('swift', 'swift_user'),
            'GROUP': self.cfg.get('swift', 'swift_group'),
            'SWIFT_DATA_LOCATION': self.cfg.get('swift', 'data_location'),
            'SWIFT_CONFIG_LOCATION': self.cfgdir,
            'SERVICE_TOKEN': self.cfg.get('passwords', 'service_token'),
            'AUTH_SERVER': self.auth_server,
            'SWIFT_HASH': self.cfg.get('passwords', 'swift_hash'),
            'NODE_PATH': '',
            'BIND_PORT': '',
            'LOG_FACILITY': '',
            'SWIFT_LOGDIR': self.logdir,
            'SWIFT_PARTITION_POWER_SIZE': self.cfg.get('swift', 'partition_power_size')
            }

    def _post_install(self):
        pass


class SwiftRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, TYPE, *args, **kargs)


def describe(opts=None):
    description = """
 Module: {module_name}
  Description:
   {description}
  Component options:
   {component_opts}
"""
    params = dict()
    params['component_opts'] = "TBD"
    params['module_name'] = __name__
    params['description'] = __doc__ or "Handles actions for the swift component."
    out = description.format(**params)
    return out.strip("\n")
