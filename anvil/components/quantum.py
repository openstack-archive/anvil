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
from anvil import component as comp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.helpers import db as dbhelper

LOG = logging.getLogger(__name__)

# Openvswitch special settings
VSWITCH_PLUGIN = 'openvswitch'

# Config files (some only modified if running as openvswitch)
PLUGIN_CONF = "plugins.ini"
QUANTUM_CONF = 'quantum.conf'
PLUGIN_LOC = ['etc']
AGENT_CONF = 'ovs_quantum_plugin.ini'
AGENT_BIN_LOC = ["quantum", "plugins", "openvswitch", 'agent']
CONFIG_FILES = [PLUGIN_CONF, AGENT_CONF]

# This db will be dropped and created
DB_NAME = 'ovs_quantum'

# Opensvswitch bridge setup/teardown/name commands
OVS_BRIDGE_DEL = ['ovs-vsctl', '--no-wait', '--', '--if-exists', 'del-br', '%OVS_BRIDGE%']
OVS_BRIDGE_ADD = ['ovs-vsctl', '--no-wait', 'add-br', '%OVS_BRIDGE%']
OVS_BRIDGE_EXTERN_ID = ['ovs-vsctl', '--no-wait', 'br-set-external-id', '%OVS_BRIDGE%', 'bridge-id', '%OVS_EXTERNAL_ID%']
OVS_BRIDGE_CMDS = [OVS_BRIDGE_DEL, OVS_BRIDGE_ADD, OVS_BRIDGE_EXTERN_ID]

# What to start (only if openvswitch enabled)
APP_Q_SERVER = 'quantum-server'
APP_Q_AGENT = 'ovs_quantum_agent.py'
APP_OPTIONS = {
    APP_Q_SERVER: ["%QUANTUM_CONFIG_FILE%"],
    APP_Q_AGENT: ["%OVS_CONFIG_FILE%", "-v"],
}


class QuantumMixin(object):
    def known_subsystems(self):
        return set(['openvswitch'])

    def _get_config_files(self):
        return list(CONFIG_FILES)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "quantum_repo"),
            'branch': ("git", "quantum_branch"),
        })
        return places


class QuantumUninstaller(QuantumMixin, comp.PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgUninstallComponent.__init__(self, *args, **kargs)


class QuantumInstaller(QuantumMixin, comp.PkgInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgInstallComponent.__init__(self, *args, **kargs)
        self.q_vswitch_agent = False
        self.q_vswitch_service = False
        plugin = self.cfg.getdefaulted("quantum", "q_plugin", VSWITCH_PLUGIN)
        if plugin == VSWITCH_PLUGIN:
            # FIXME: Make these subsystems
            self.q_vswitch_agent = True
            self.q_vswitch_service = True

    def _config_adjust(self, contents, config_fn):
        if config_fn == PLUGIN_CONF and self.q_vswitch_service:
            # Need to fix the "Quantum plugin provider module"
            with io.BytesIO(contents) as stream:
                config = cfg.RewritableConfigParser()
                config.readfp(stream)
                config.set("plugin", "provider", "quantum.plugins.openvswitch.ovs_quantum_plugin.OVSQuantumPlugin")
                contents = config.stringify(config_fn)
            return contents
        elif config_fn == AGENT_CONF and self.q_vswitch_agent:
            # Need to adjust the sql connection
            with io.BytesIO(contents) as stream:
                config = cfg.RewritableConfigParser()
                config.readfp(stream)
                config.set("database", "sql_connection", dbhelper.fetch_dbdsn(self.cfg, DB_NAME, utf8=True))
                contents = config.stringify(config_fn)
            return contents
        else:
            return comp.PkgInstallComponent._config_adjust(self, contents, config_fn)

    def _setup_bridge(self):
        if not self.q_vswitch_agent or not self.get_option('ovs-bridge-init'):
            return
        else:
            bridge = self.cfg.getdefaulted("quantum", "ovs_bridge", 'br-int')
            LOG.info("Fixing up ovs bridge named: %s", colorizer.quote(bridge))
            external_id = self.cfg.getdefaulted("quantum", 'ovs_bridge_external_name', bridge)
            params = dict()
            params['OVS_BRIDGE'] = bridge
            params['OVS_EXTERNAL_ID'] = external_id
            cmds = list()
            for cmd_templ in OVS_BRIDGE_CMDS:
                cmds.append({
                    'cmd': cmd_templ,
                    'run_as_root': True,
                })
            utils.execute_template(*cmds, params=params)

    def post_install(self):
        comp.PkgInstallComponent.post_install(self)
        self._setup_db()
        self._setup_bridge()

    def _setup_db(self):
        if not self.q_vswitch_service or not self.get_option('ovs-bridge-init'):
            return
        else:
            dbhelper.drop_db(self.cfg, self.distro, DB_NAME)
            dbhelper.create_db(self.cfg, self.distro, DB_NAME, utf8=True)

    def _get_source_config(self, config_fn):
        if config_fn == PLUGIN_CONF:
            src_fn = sh.joinpths(self.get_option('app_dir'), 'etc', config_fn)
            contents = sh.load_file(src_fn)
            return (src_fn, contents)
        elif config_fn == AGENT_CONF:
            # WHY U SO BURIED....
            src_fn = sh.joinpths(self.get_option('app_dir'), 'etc', 'quantum', 'plugins', 'openvswitch', config_fn)
            contents = sh.load_file(src_fn)
            return (src_fn, contents)
        else:
            return comp.PkgInstallComponent._get_source_config(self, config_fn)


class QuantumRuntime(QuantumMixin, comp.ProgramRuntime):
    def __init__(self, *args, **kargs):
        comp.ProgramRuntime.__init__(self, *args, **kargs)
        self.q_vswitch_agent = False
        self.q_vswitch_service = False
        plugin = self.cfg.getdefaulted("quantum", "q_plugin", VSWITCH_PLUGIN)
        if plugin == VSWITCH_PLUGIN:
            # Default to on if not specified
            self.q_vswitch_agent = True
            self.q_vswitch_service = True

    def _get_apps_to_start(self):
        app_list = comp.ProgramRuntime._get_apps_to_start(self)
        if self.q_vswitch_service:
            app_list.append({
                'name': APP_Q_SERVER,
                'path': sh.joinpths(self.get_option('app_dir'), 'bin', APP_Q_SERVER),
            })
        if self.q_vswitch_agent:
            app_list.append({
                'name': APP_Q_AGENT,
                # WHY U SO BURIED....
                'path': sh.joinpths(self.get_option('app_dir'), "quantum", "plugins", "openvswitch", 'agent', APP_Q_AGENT)
            })
        return app_list

    def _get_app_options(self, app_name):
        return APP_OPTIONS.get(app_name)

    def _get_param_map(self, app_name):
        param_dict = comp.ProgramRuntime._get_param_map(self, app_name)
        if app_name == APP_Q_AGENT:
            param_dict['OVS_CONFIG_FILE'] = sh.joinpths(self.get_option('cfg_dir'), AGENT_CONF)
        elif app_name == APP_Q_SERVER:
            param_dict['QUANTUM_CONFIG_FILE'] = sh.joinpths(self.get_option('cfg_dir'), QUANTUM_CONF)
        return param_dict
