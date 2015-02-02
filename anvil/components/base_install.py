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
from anvil import utils

from anvil.packaging.helpers import pip_helper

LOG = logging.getLogger(__name__)

# Potential files that can hold a projects requirements...
REQUIREMENT_FILES = [
    'pip-requires',
    'requirements.txt',
    'requirements-py2.txt',
]

TEST_REQUIREMENT_FILES = [
    'test-requires',
    'test-requirements.txt',
]


class InstallableMixin(base.Component):
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
                LOG.debug("Configuring file %s ---> %s.", source_fn, tgt_fn)
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


class PythonComponent(base.BasicComponent):
    def __init__(self, *args, **kargs):
        super(PythonComponent, self).__init__(*args, **kargs)
        self._origins_fn = kargs['origins_fn']
        app_dir = self.get_option('app_dir')
        tools_dir = sh.joinpths(app_dir, 'tools')
        self.requires_files = []
        self.test_requires_files = []
        for path in [app_dir, tools_dir]:
            for req_fn in REQUIREMENT_FILES:
                self.requires_files.append(sh.joinpths(path, req_fn))
            for req_fn in TEST_REQUIREMENT_FILES:
                self.test_requires_files.append(sh.joinpths(path, req_fn))

    def config_params(self, config_fn):
        mp = dict(self.params)
        if config_fn:
            mp['CONFIG_FN'] = config_fn
        return mp

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
