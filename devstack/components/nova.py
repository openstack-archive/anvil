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

from devstack import component as comp
from devstack import log as logging
from devstack import settings
from devstack import utils
from devstack import shell as sh
from devstack.components import db
from devstack.components import nova_conf as nc

LOG = logging.getLogger("devstack.components.nova")

API_CONF = "nova.conf"
PASTE_CONF = 'nova-api-paste.ini'
CONFIGS = [API_CONF]

DB_NAME = "nova"
BIN_DIR = 'bin'
TYPE = settings.NOVA

#what to start
APP_OPTIONS = {
    'nova-api': [],
    settings.NCPU: [],
    settings.NVOL: [],
    'nova-network': [],
    'nova-scheduler': []
}

# In case we need to map names to the image to run
APP_NAME_MAP = {
    settings.NCPU: 'nova-compute',
    settings.NVOL: 'nova-volume',
}
CONFIG_ACTUAL_DIR = 'etc'
BIN_DIR = 'bin'
# FIXME, need base bin dir
DB_SYNC = ['/bin/nova-manage', 'db', 'sync']


class NovaUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)
        #self.cfgdir = joinpths(self.appdir, CONFIG_ACTUAL_DIR)


class NovaInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.git_repo = self.cfg.get("git", "nova_repo")
        self.git_branch = self.cfg.get("git", "nova_branch")
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)

    def get_pkglist(self):
        pkgs = comp.PkgInstallComponent.get_pkglist(self)
        LOG.debug("pkg list from parent: %s" % (pkgs))
        # Walk through the subcomponents (like 'vol' and 'cpu') and add those
        # those packages as well. (Let utils.get_pkg_list handle any missing
        # entries
        LOG.debug("get_pkglist looking for extras: %s" % (self.component_opts))
        for cname in self.component_opts:
            pkgs.update(utils.get_pkg_list(self.distro, cname))
        return pkgs

    def _get_download_locations(self):
        places = comp.PythonInstallComponent._get_download_locations(self)
        places.append({
            'uri': self.git_repo,
            'branch': self.git_branch,
        })
        return places

    def post_install(self):
        parent_result = comp.PkgInstallComponent.post_install(self)
        #extra actions to do nova setup
        LOG.debug("Setting up our database")
        self._setup_db()
        # Need to do db sync
        # Need to do nova-managber create private
        # TBD, do we need to so nova-api start first?
        # If using q-qvc, skip
        #   $NOVA_DIR/bin/nova-manage floating create $FLOATING_RANGE
        #   $NOVA_DIR/bin/nova-manage floating create --ip_range=$TEST_FLOATING_RANGE --pool=$TEST_FLOATING_POOL
        return parent_result

    def _setup_db(self):
        LOG.debug("setting up nova DB")
        db.drop_db(self.cfg, DB_NAME)
        db.create_db(self.cfg, DB_NAME)

    def _generate_nova_conf(self):
        LOG.debug("Generating dynamic content for nova configuration")
        dirs = dict()
        dirs['app'] = self.appdir
        dirs['cfg'] = self.cfgdir
        dirs['bin'] = self.bindir
        conf_gen = nc.NovaConfigurator(self.cfg, self.all_components)
        nova_conf = conf_gen.configure(dirs)
        tgtfn = self._get_target_config_name(API_CONF)
        LOG.info("Created nova configuration:")
        LOG.info(nova_conf)
        LOG.debug("Placing it in %s" % (tgtfn))
        sh.write_file(tgtfn, nova_conf)
        #we configured one file, return that we did that
        return 1

    def _configure_files(self):
        return self._generate_nova_conf()


class NovaRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, TYPE, *args, **kargs)

    def _get_aps_to_start(self):
        # Check if component_opts was set to a subset of apps to be started
        apps = list()
        if (not self.component_opts and len(self.component_opts) > 0):
            LOG.debug("Attempt to use subset of components:%s" % (self.component_opts))
            # check if the specified sub components exist
            delta = set(self.component_opts) - set(APP_OPTIONS.keys())
            if (delta):
                # FIXME, error, something was specified that we don't have
                LOG.error("sub items that we don't know about:%s" % delta)
            else:
                apps = self.component_opts
        else:
            apps = APP_OPTIONS.keys()

        result = list()
        for app_name in apps:
            if (app_name in APP_NAME_MAP):
                app_name = APP_NAME_MAP.get(app_name)
            list.append({
                'name': app_name,
                'path': sh.joinpths(self.appdir, BIN_DIR, app_name),
            })
        return result

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)
