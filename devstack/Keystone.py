# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import Pip
import Logger
import Db

#TODO fix these
from Util import (KEYSTONE,
                  CONFIG_DIR,
                  NOVA, GLANCE, SWIFT,
                  get_host_ip,
                  execute_template,
                  param_replace)
from Component import (PythonUninstallComponent,
                PythonInstallComponent, PythonRuntime)
from Shell import (mkdirslist, unlink, touch_file, joinpths)

LOG = Logger.getLogger("install.keystone")

TYPE = KEYSTONE
ROOT_CONF = "keystone.conf"
CONFIGS = [ROOT_CONF]
BIN_DIR = "bin"
DB_NAME = "keystone"

#what to start
APP_OPTIONS = {
    'keystone': ['--config-file', joinpths('%ROOT%', "config", ROOT_CONF), "--verbose"],
}


class KeystoneUninstaller(PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = joinpths(self.appdir, CONFIG_DIR)
        self.bindir = joinpths(self.appdir, BIN_DIR)


class KeystoneInstaller(PythonInstallComponent):
    def __init__(self, *args, **kargs):
        PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.gitloc = self.cfg.get("git", "keystone_repo")
        self.brch = self.cfg.get("git", "keystone_branch")
        self.cfgdir = joinpths(self.appdir, CONFIG_DIR)
        self.bindir = joinpths(self.appdir, BIN_DIR)

    def _get_download_location(self):
        return (self.gitloc, self.brch)

    def install(self):
        parent_res = PythonInstallComponent.install(self)
        #adjust db
        self._setup_db()
        #setup any data
        self._setup_data()
        return parent_res

    def _get_config_files(self):
        return list(CONFIGS)

    def _setup_db(self):
        Db.drop_db(self.cfg, DB_NAME)
        Db.create_db(self.cfg, DB_NAME)

    def _setup_data(self):
        params = self._get_param_map()
        cmds = _keystone_setup_cmds(self.othercomponents)
        execute_template(*cmds, params=params, ignore_missing=True)

    def _config_adjust(self, contents, fn):
        lines = contents.splitlines()
        for line in lines:
            cleaned = line.strip()
            if(len(cleaned) == 0 or
                cleaned[0] == '#' or cleaned[0] == '['):
                #not useful to examine these
                continue
            pieces = cleaned.split("=", 1)
            if(len(pieces) != 2):
                continue
            key = pieces[0].strip()
            val = pieces[1].strip()
            if(len(key) == 0 or len(val) == 0):
                continue
            #now we take special actions
            if(key == 'log_file'):
                # Ensure that we can write to the log file
                dirname = os.path.dirname(val)
                if(len(dirname)):
                    dirsmade = mkdirslist(dirname)
                    # This trace is used to remove the dirs created
                    self.tracewriter.dir_made(*dirsmade)
                # Destroy then recreate it
                unlink(val)
                touch_file(val)
                self.tracewriter.file_touched(val)
        return contents

    def _get_param_map(self, fn=None):
        #these be used to fill in the configuration/cmds +
        #params with actual values
        mp = dict()
        mp['DEST'] = self.appdir
        mp['SQL_CONN'] = self.cfg.get_dbdsn(DB_NAME)
        mp['ADMIN_PASSWORD'] = self.cfg.getpw('passwords', 'horizon_keystone_admin')
        mp['HOST_IP'] = get_host_ip(self.cfg)
        mp['SERVICE_TOKEN'] = self.cfg.getpw("passwords", "service_token")
        mp['BIN_DIR'] = self.bindir
        mp['CONFIG_FILE'] = joinpths(self.cfgdir, ROOT_CONF)
        return mp


class KeystoneRuntime(PythonRuntime):
    def __init__(self, *args, **kargs):
        PythonRuntime.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = joinpths(self.appdir, CONFIG_DIR)
        self.bindir = joinpths(self.appdir, BIN_DIR)

    def _get_apps_to_start(self):
        return sorted(APP_OPTIONS.keys())

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)


# Keystone setup commands are the the following
def _keystone_setup_cmds(components):

    # See http://keystone.openstack.org/man/keystone-manage.html

    root_cmd = ["%BIN_DIR%/keystone-manage", '--config-file=%CONFIG_FILE%']

    # Tenants
    tenant_cmds = [
        {
            "cmd": root_cmd + ["tenant", "add", "admin"],
        },
        {
            "cmd": root_cmd + ["tenant", "add", "demo"]
        },
        {
            "cmd": root_cmd + ["tenant", "add", "invisible_to_admin"]
        },
    ]

    # Users
    user_cmds = [
        {
            "cmd": root_cmd + ["user", "add", "admin", "%ADMIN_PASSWORD%"]
        },
        {
            "cmd": root_cmd + ["user", "add", "demo", "%ADMIN_PASSWORD%"]
        },
    ]

    # Roles
    role_cmds = [
        {
            "cmd": root_cmd + ["role", "add", "Admin"]
        },
        {
            "cmd": root_cmd + ["role", "add", "Member"]
        },
        {
            "cmd": root_cmd + ["role", "add", "KeystoneAdmin"]
        },
        {
            "cmd": root_cmd + ["role", "add", "KeystoneServiceAdmin"]
        },
        {
            "cmd": root_cmd + ["role", "add", "sysadmin"]
        },
        {
            "cmd": root_cmd + ["role", "add", "netadmin"]
        },
        {
            "cmd": root_cmd + ["role", "grant", "Admin", "admin", "admin"]
        },
        {
            "cmd": root_cmd + ["role", "grant", "Member", "demo", "demo"]
        },
        {
            "cmd": root_cmd + ["role", "grant", "sysadmin", "demo", "demo"]
        },
        {
            "cmd": root_cmd + ["role", "grant", "netadmin", "demo", "demo"]
        },
        {
            "cmd": root_cmd + ["role", "grant", "Member", "demo", "invisible_to_admin"]
        },
        {
            "cmd": root_cmd + ["role", "grant", "Admin", "admin", "demo"]
        },
        {
            "cmd": root_cmd + ["role", "grant", "Admin", "admin"]
        },
        {
            "cmd": root_cmd + ["role", "grant", "KeystoneAdmin", "admin"]
        },
        {
            "cmd": root_cmd + ["role", "grant", "KeystoneServiceAdmin", "admin"]
        }
    ]

    # Services
    services = []
    services.append({
        "cmd": root_cmd + ["service", "add", "keystone", "identity", "Keystone Identity Service"]
    })

    if(NOVA in components):
        services.append({
                "cmd": root_cmd + ["service", "add", "nova", "compute", "Nova Compute Service"]
        })
        services.append({
                "cmd": root_cmd + ["service", "add", "ec2", "ec2", "EC2 Compatability Layer"]
        })

    if(GLANCE in components):
        services.append({
                "cmd": root_cmd + ["service", "add", "glance", "image", "Glance Image Service"]
        })

    if(SWIFT in components):
        services.append({
                "cmd": root_cmd + ["service", "add", "swift", "object-store", "Swift Service"]
        })

    # Endpoint templates
    endpoint_templates = list()
    endpoint_templates.append({
            "cmd": root_cmd + ["endpointTemplates", "add",
                "RegionOne", "keystone",
                "http://%HOST_IP%:5000/v2.0",
                "http://%HOST_IP%:35357/v2.0",
                "http://%HOST_IP%:5000/v2.0",
                "1",
                "1"
            ]
    })

    if(NOVA in components):
        endpoint_templates.append({
                "cmd": root_cmd + ["endpointTemplates", "add",
                    "RegionOne", "nova",
                    "http://%HOST_IP%:8774/v1.1/%tenant_id%",
                    "http://%HOST_IP%:8774/v1.1/%tenant_id%",
                    "http://%HOST_IP%:8774/v1.1/%tenant_id%",
                    "1",
                    "1"
            ]
        })
        endpoint_templates.append({
                "cmd": root_cmd + ["endpointTemplates", "add",
                    "RegionOne", "ec2",
                    "http://%HOST_IP%:8773/services/Cloud",
                    "http://%HOST_IP%:8773/services/Admin",
                    "http://%HOST_IP%:8773/services/Cloud",
                    "1",
                    "1"
            ]
        })

    if(GLANCE in components):
        endpoint_templates.append({
                "cmd": root_cmd + ["endpointTemplates", "add",
                    "RegionOne", "glance",
                    "http://%HOST_IP%:9292/v1.1/%tenant_id%",
                    "http://%HOST_IP%:9292/v1.1/%tenant_id%",
                    "http://%HOST_IP%:9292/v1.1/%tenant_id%",
                    "1",
                    "1"
            ]
        })

    if(SWIFT in components):
        endpoint_templates.append({
                "cmd": root_cmd + ["endpointTemplates", "add",
                    "RegionOne", "swift",
                    "http://%HOST_IP%:8080/v1/AUTH_%tenant_id%",
                    "http://%HOST_IP%:8080/",
                    "http://%HOST_IP%:8080/v1/AUTH_%tenant_id%",
                    "1",
                    "1"
            ]
        })

    # Tokens
    tokens = [
        {
            "cmd": root_cmd + ["token", "add", "%SERVICE_TOKEN%", "admin", "admin", "2015-02-05T00:00"]
        },
    ]

    # EC2 related creds - note we are setting the secret key to ADMIN_PASSWORD
    # but keystone doesn't parse them - it is just a blob from keystone's
    # point of view
    ec2_creds = []
    if(NOVA in components):
        ec2_creds = [
            {
                "cmd": root_cmd + ["credentials", "add",
                        "admin", "EC2", "admin", "%ADMIN_PASSWORD%", "admin"]
            },
            {
                "cmd": root_cmd + ["credentials", "add",
                    "demo", "EC2", "demo", "%ADMIN_PASSWORD%", "demo"]
            }
        ]

    # Order matters here...
    all_cmds = tenant_cmds + user_cmds + role_cmds + services + endpoint_templates + tokens + ec2_creds
    return all_cmds
