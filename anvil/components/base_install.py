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
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils

from anvil.packaging.helpers import pip_helper

LOG = logging.getLogger(__name__)


class InstallableMixin(base.Component):
    def __init__(self, *args, **kargs):
        super(InstallableMixin, self).__init__(*args, **kargs)

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


class PythonComponent(base.BasicComponent):
    def __init__(self, *args, **kargs):
        super(PythonComponent, self).__init__(*args, **kargs)
        app_dir = self.get_option('app_dir')
        tools_dir = sh.joinpths(app_dir, 'tools')
        self.requires_files = [
            sh.joinpths(tools_dir, 'pip-requires'),
            sh.joinpths(app_dir, 'requirements.txt'),
        ]
        self.test_requires_files = [
            sh.joinpths(tools_dir, 'test-requires'),
            sh.joinpths(app_dir, 'test-requirements.txt'),
        ]
        self._origins_fn = kargs['origins_fn']

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

    def download(self):
        """Download sources needed to build the component, if any."""
        target_dir = self.get_option('app_dir')
        download_cfg = utils.load_yaml(self._origins_fn).get(self.name, {})
        if not target_dir or not download_cfg:
            return []

        uri = download_cfg.pop('repo', None)
        if not uri:
            raise ValueError(("Could not find repo uri for %r component from the %r "
                              "config file." % (self.name, self._origins_fn)))

        uris = [uri]
        utils.log_iterable(uris, logger=LOG,
                           header="Downloading from %s uris" % (len(uris)))
        sh.mkdirslist(target_dir, tracewriter=self.tracewriter)
        # This is used to delete what is downloaded (done before
        # fetching to ensure its cleaned up even on download failures)
        self.tracewriter.download_happened(target_dir, uri)
        down.GitDownloader(uri, target_dir, **download_cfg).download()
        return uris

    @property
    def egg_info(self):
        egg_info = pip_helper.get_directory_details(self.get_option('app_dir')).copy()
        read_reqs = pip_helper.read_requirement_files
        egg_info['dependencies'] = read_reqs(self.requires_files)
        egg_info['test_dependencies'] = read_reqs(self.test_requires_files)
        return egg_info


class PkgInstallComponent(base.BasicComponent, InstallableMixin):
    pass


class PythonInstallComponent(PythonComponent, InstallableMixin):
    pass


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
