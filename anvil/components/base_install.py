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

from anvil.components import base
from anvil import downloader as down
from anvil import log as logging
from anvil import patcher
from anvil import settings
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils

from anvil.packaging.helpers import pip_helper

from anvil.components.configurators import base as conf

LOG = logging.getLogger(__name__)


class PkgInstallComponent(base.Component):
    def __init__(self, *args, **kargs):
        super(PkgInstallComponent, self).__init__(*args, **kargs)
        trace_fn = tr.trace_filename(self.get_option('trace_dir'), 'created')
        self.tracewriter = tr.TraceWriter(trace_fn, break_if_there=False)
        self.configurator = conf.Configurator(self)

    def _get_download_config(self):
        return None

    def _get_download_location(self):
        key = self._get_download_config()
        if not key:
            return (None, None)
        uri = self.get_option(key, default_value='').strip()
        if not uri:
            raise ValueError(("Could not find uri in config to download "
                              "from option %s") % (key))
        return (uri, self.get_option('app_dir'))

    def download(self):
        (from_uri, target_dir) = self._get_download_location()
        if not from_uri and not target_dir:
            return []
        else:
            uris = [from_uri]
            utils.log_iterable(uris, logger=LOG,
                               header="Downloading from %s uris" % (len(uris)))
            sh.mkdirslist(target_dir, tracewriter=self.tracewriter)
            # This is used to delete what is downloaded (done before
            # fetching to ensure its cleaned up even on download failures)
            self.tracewriter.download_happened(target_dir, from_uri)
            fetcher = down.GitDownloader(self.distro, from_uri, target_dir)
            fetcher.download()
            return uris

    def list_patches(self, section):
        what_patches = self.get_option('patches', section)
        if not what_patches:
            what_patches = [sh.joinpths(settings.CONFIG_DIR, 'patches',
                                        self.name, section)]
        canon_what_patches = []
        for path in what_patches:
            if sh.isdir(path):
                patches = sorted(fn for fn in sh.listdir(path, files_only=True)
                                 if fn.endswith('patch'))
                canon_what_patches.extend(patches)
            elif sh.isfile(path):
                canon_what_patches.append(path)
        return canon_what_patches

    def patch(self, section):
        canon_what_patches = self.list_patches(section)
        if canon_what_patches:
            (_from_uri, target_dir) = self._get_download_location()
            patcher.apply_patches(canon_what_patches, target_dir)

    def config_params(self, config_fn):
        mp = dict(self.params)
        if config_fn:
            mp['CONFIG_FN'] = config_fn
        return mp

    @property
    def packages(self):
        return self.extended_packages()

    def extended_packages(self):
        pkg_list = self.get_option('packages', default_value=[])
        if not pkg_list:
            pkg_list = []
        for name, values in self.subsystems.items():
            if 'packages' in values:
                LOG.debug("Extending package list with packages for subsystem: %r", name)
                pkg_list.extend(values.get('packages'))
        return pkg_list

    def pre_install(self):
        pkgs = self.packages
        for p in pkgs:
            installer = self.distro.install_helper_class(distro=self.distro)
            installer.pre_install(p, self.params)

    def post_install(self):
        pkgs = self.packages
        for p in pkgs:
            installer = self.distro.install_helper_class(distro=self.distro)
            installer.post_install(p, self.params)

    def _configure_files(self):
        config_fns = self.configurator.config_files
        if config_fns:
            utils.log_iterable(config_fns, logger=LOG,
                               header="Configuring %s files" % (len(config_fns)))
            for fn in config_fns:
                tgt_fn = self.configurator.target_config(fn)
                sh.mkdirslist(sh.dirname(tgt_fn), tracewriter=self.tracewriter)
                (source_fn, contents) = self.configurator.source_config(fn)
                LOG.debug("Configuring file %s ---> %s.", (source_fn), (tgt_fn))
                contents = self.configurator.config_param_replace(fn, contents, self.config_params(fn))
                contents = self.configurator.config_adjust(contents, fn)
                sh.write_file(tgt_fn, contents, tracewriter=self.tracewriter)
        return len(config_fns)

    def configure(self):
        files = self._configure_files()
        if sh.isdir(self.cfg_dir):
            uid = None
            gid = None
            try:
                uid = sh.getuid(self.name)
                gid = sh.getgid(self.name)
            except (KeyError, AttributeError):
                LOG.warn("Unable to find uid & gid for user & group %s", self.name)
            if uid is not None and gid is not None:
                try:
                    sh.chown_r(self.cfg_dir, uid, gid)
                except Exception as e:
                    LOG.warn("Failed to change the ownership of %s to %s:%s due to: %s",
                             self.cfg_dir, uid, gid, e)
        return files


class PythonInstallComponent(PkgInstallComponent):
    def __init__(self, *args, **kargs):
        PkgInstallComponent.__init__(self, *args, **kargs)
        app_dir = self.get_option('app_dir')
        tools_dir = sh.joinpths(app_dir, 'tools')
        self.requires_files = [
            sh.joinpths(tools_dir, 'pip-requires'),
            sh.joinpths(app_dir, 'requirements.txt'),
        ]
        if self.get_bool_option('use_tests_requires', default_value=True):
            self.requires_files.append(sh.joinpths(tools_dir, 'test-requires'))
            self.requires_files.append(sh.joinpths(app_dir,
                                                   'test-requirements.txt'))
        self._egg_info = None

    def _get_download_config(self):
        return 'get_from'

    @property
    def egg_info(self):
        if self._egg_info is None:
            egg = pip_helper.get_directory_details(self.get_option('app_dir'))
            self._egg_info = egg
        return self._egg_info


class PkgUninstallComponent(base.Component):
    def __init__(self, *args, **kargs):
        super(PkgUninstallComponent, self).__init__(*args, **kargs)
        trace_fn = tr.trace_filename(self.get_option('trace_dir'), 'created')
        self.tracereader = tr.TraceReader(trace_fn)

    def unconfigure(self):
        pass

    def post_uninstall(self):
        self._uninstall_files()
        self._uninstall_dirs()

    def pre_uninstall(self):
        pass

    def uninstall(self):
        pass

    def _uninstall_files(self):
        files_touched = self.tracereader.files_touched()
        files_alive = filter(sh.isfile, files_touched)
        if files_alive:
            utils.log_iterable(files_alive, logger=LOG,
                               header="Removing %s miscellaneous files" % (len(files_alive)))
            for fn in files_alive:
                sh.unlink(fn)

    def _uninstall_dirs(self):
        dirs_made = self.tracereader.dirs_made()
        dirs_alive = filter(sh.isdir, dirs_made)
        if dirs_alive:
            utils.log_iterable(dirs_alive, logger=LOG,
                               header="Removing %s created directories" % (len(dirs_alive)))
            for dir_name in dirs_alive:
                sh.deldir(dir_name)
