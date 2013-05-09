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

import io

from anvil import cfg
from anvil import colorizer
from anvil import components as comp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.components.helpers import db as dbhelper
from anvil.components.helpers import keystone as khelper
from anvil.components.helpers import nova as nhelper
from anvil.components.helpers import rabbit as rhelper

LOG = logging.getLogger(__name__)

# This db will be dropped and created
DB_NAME = "quantum"

# Sync db command
# FIXME(aababilov)
SYNC_DB_CMD = [sh.joinpths("$BIN_DIR", "quantum-db-manage"),
               "sync"]

# Config files/sections
PASTE_CONF = "api-paste.ini"

# build PLUGIN_CONFS with
# for i in *; do
#     echo '    "'$i'": ['
#     for j in $i/*; do echo '        "plugins/'$j'",'; done
#     echo "    ],"
# done
PLUGIN_CONFS = {
    "bigswitch": [
        "plugins/bigswitch/restproxy.ini",
    ],
    "brocade": [
        "plugins/brocade/brocade.ini",
    ],
    "cisco": [
        "plugins/cisco/cisco_plugins.ini",
        "plugins/cisco/credentials.ini",
        "plugins/cisco/db_conn.ini",
        "plugins/cisco/l2network_plugin.ini",
        "plugins/cisco/nexus.ini",
    ],
    "hyperv": [
        "plugins/hyperv/hyperv_quantum_plugin.ini",
    ],
    "linuxbridge": [
        "plugins/linuxbridge/linuxbridge_conf.ini",
    ],
    "metaplugin": [
        "plugins/metaplugin/metaplugin.ini",
    ],
    "midonet": [
        "plugins/midonet/midonet.ini",
    ],
    "nec": [
        "plugins/nec/nec.ini",
    ],
    "nicira": [
        "plugins/nicira/nvp.ini",
    ],
    "openvswitch": [
        "plugins/openvswitch/ovs_quantum_plugin.ini",
    ],
    "plumgrid": [
        "plugins/plumgrid/plumgrid.ini",
    ],
    "ryu": [
        "plugins/ryu/ryu.ini",
    ],
}

API_CONF = "quantum.conf"

CONFIGS = [PASTE_CONF, API_CONF]

BIN_DIR = "bin"

CORE_PLUGIN_CLASSES = {
    "linuxbridge":
    "quantum.plugins.linuxbridge.lb_quantum_plugin.LinuxBridgePluginV2",
}


class QuantumUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        super(QuantumUninstaller, self).__init__(*args, **kargs)
        self.bin_dir = sh.joinpths(self.get_option("app_dir"), BIN_DIR)


class QuantumInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        super(QuantumInstaller, self).__init__(*args, **kargs)
        self.bin_dir = sh.joinpths(self.get_option("app_dir"), BIN_DIR)
        self.core_plugin = self.get_option("core_plugin")
        self.plugin_confs = PLUGIN_CONFS[self.core_plugin]

    @property
    def config_files(self):
        return list(CONFIGS) + self.plugin_confs

    def post_install(self):
        super(QuantumInstaller, self).post_install()
        if self.get_bool_option("db-sync"):
            self._setup_db()
            self._sync_db()

    def _filter_pip_requires(self, fn, lines):
        # Take out entries that aren't really always needed or are
        # resolved/installed by anvil during installation in the first
        # place..
        return [l for l in lines
                if not utils.has_any(l.lower(), "oslo.config")]

    def _setup_db(self):
        dbhelper.drop_db(
            distro=self.distro,
            dbtype=self.get_option("db", "type"),
            dbname=DB_NAME,
            **utils.merge_dicts(self.get_option("db"),
                                dbhelper.get_shared_passwords(self)))
        dbhelper.create_db(
            distro=self.distro,
            dbtype=self.get_option("db", "type"),
            dbname=DB_NAME,
            **utils.merge_dicts(self.get_option("db"),
                                dbhelper.get_shared_passwords(self)))

    def _sync_db(self):
        LOG.info("Syncing quantum to database: %s", colorizer.quote(DB_NAME))
        #cmds = [{"cmd": SYNC_DB_CMD, "run_as_root": True}]
        #utils.execute_template(*cmds, cwd=self.bin_dir,
        # params=self.config_params(None))

    def source_config(self, config_fn):
        if (config_fn.startswith("plugins") or
                config_fn.startswith("rootwrap.d")):
            real_fn = "quantum/%s" % config_fn
        else:
            real_fn = config_fn
        fn = sh.joinpths(self.get_option("app_dir"), "etc", real_fn)
        return (fn, sh.load_file(fn))

    def _fetch_keystone_params(self):
        params = khelper.get_shared_params(
            ip=self.get_option("ip"),
            service_user="quantum",
            **utils.merge_dicts(self.get_option("keystone"),
                                khelper.get_shared_passwords(self)))
        return {
            "auth_host": params["endpoints"]["admin"]["host"],
            "auth_port": params["endpoints"]["admin"]["port"],
            "auth_protocol": params["endpoints"]["admin"]["protocol"],
            # This uses the public uri not the admin one...
            "auth_uri": params["endpoints"]["public"]["uri"],
            "admin_tenant_name": params["service_tenant"],
            "admin_user": params["service_user"],
            "admin_password": params["service_password"],
        }

    def _config_adjust(self, contents, name):
        available_adjusters = {
            PASTE_CONF: self.make_adjust_paste,
            API_CONF: self.make_adjust_api_conf,
            PLUGIN_CONFS["linuxbridge"][0]: self.make_plugin_conf_linuxbridge,
        }
        adjuster = available_adjusters.get(name)
        if adjuster:
            if isinstance(contents, unicode):
                contents = contents.encode("utf-8")
            with io.BytesIO(contents) as stream:
                config = cfg.create_parser(cfg.RewritableConfigParser, self)
                config.readfp(stream)
                adjuster(cfg.DefaultConf(config))
                contents = config.stringify(name)
        return contents

    # TODO(aababilov): move to base class
    def make_sql_connection(self, dbname):
        return dbhelper.fetch_dbdsn(
            dbname=dbname,
            utf8=True,
            dbtype=self.get_option('db', 'type'),
            **utils.merge_dicts(self.get_option('db'),
                                dbhelper.get_shared_passwords(self)))

    # TODO(aababilov): move to base class
    def setup_rpc(self, conf, rpc_backend):
        # How is your message queue setup?
        mq_type = nhelper.canon_mq_type(self.get_option('mq-type'))
        if mq_type == 'rabbit':
            conf.add(
                'rabbit_host',
                self.get_option(
                    'rabbit', 'host', default_value=self.get_option('ip')))
            conf.add(
                'rabbit_password', rhelper.get_shared_passwords(self)['pw'])
            conf.add(
                'rabbit_userid', self.get_option('rabbit', 'user_id'))
            conf.add(
                'rpc_backend', rpc_backend)

    def make_plugin_conf_linuxbridge(self, plugin_conf):
        plugin_conf.add_with_section(
            "VLANS",
            "network_vlan_ranges",
            self.get_option("network_vlan_ranges"))
        plugin_conf.add_with_section(
            "DATABASE",
            "sql_connection",
            self.make_sql_connection(DB_NAME))
        plugin_conf.add_with_section(
            "LINUX_BRIDGE",
            "physical_interface_mappings",
            self.get_option("physical_interface_mappings"))

    def make_adjust_api_conf(self, quantum_conf):
        quantum_conf.add("core_plugin", CORE_PLUGIN_CLASSES[self.core_plugin])
        quantum_conf.add('auth_strategy', 'keystone')
        quantum_conf.add("api_paste_config", self.target_config(PASTE_CONF))
        # TODO(aababilov): add debug to other services conf files
        quantum_conf.add('debug', self.get_bool_option("debug"))

        # Setup the interprocess locking directory
        # (don't put me on shared storage)
        lock_path = self.get_option('lock_path')
        if not lock_path:
            lock_path = sh.joinpths(self.get_option('component_dir'), 'locks')
        sh.mkdirslist(lock_path, tracewriter=self.tracewriter)
        quantum_conf.add('lock_path', lock_path)

        self.setup_rpc(quantum_conf, 'quantum.openstack.common.rpc.impl_kombu')

        quantum_conf.current_section = "keystone_authtoken"
        for (k, v) in self._fetch_keystone_params().items():
            quantum_conf.add(k, v)

    def make_adjust_paste(self, api_paste):
        api_paste.current_section = "filter:authtoken"
        for (k, v) in self._fetch_keystone_params().items():
            api_paste.add(k, v)

    def _config_param_replace(self, config_fn, contents, parameters):
        if config_fn in [PASTE_CONF, API_CONF]:
            # We handle these ourselves
            return contents
        else:
            return super(QuantumInstaller, self)._config_param_replace(
                config_fn, contents, parameters)

    def config_params(self, config_fn):
        # These be used to fill in the configuration params
        mp = super(QuantumInstaller, self).config_params(config_fn)
        mp["BIN_DIR"] = self.bin_dir
        return mp


class QuantumRuntime(comp.PythonRuntime):

    system = "quantum"

    def __init__(self, *args, **kargs):
        super(QuantumRuntime, self).__init__(*args, **kargs)

        # TODO(aababilov): move to base class
        self.bin_dir = sh.joinpths(self.get_option("app_dir"), BIN_DIR)
        self.config_path = sh.joinpths(self.get_option("cfg_dir"), API_CONF)

    # TODO(aababilov): move to base class
    @property
    def applications(self):
        apps = []
        for (name, _values) in self.subsystems.items():
            name = "%s-%s" % (self.system, name.lower())
            path = sh.joinpths(self.bin_dir, name)
            if sh.is_executable(path):
                apps.append(comp.Program(
                    name, path, argv=self._fetch_argv(name)))
        return apps

    def app_params(self, program):
        params = comp.PythonRuntime.app_params(self, program)
        params["CFG_FILE"] = self.config_path
        return params

    def _fetch_argv(self, name):
        return [
            "--config-file", "$CFG_FILE",
        ]
