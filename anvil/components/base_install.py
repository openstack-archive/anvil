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

from anvil import colorizer
from anvil.components import base
from anvil import downloader as down
from anvil import importer
from anvil import log as logging
from anvil import patcher
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils

from anvil.components.configurators import base as conf

LOG = logging.getLogger(__name__)

# Cache of accessed packagers
_PACKAGERS = {}


def make_packager(package, default_class, **kwargs):
    packager_name = package.get('packager_name') or ''
    packager_name = packager_name.strip()
    if packager_name:
        packager_cls = importer.import_entry_point(packager_name)
    else:
        packager_cls = default_class
    if packager_cls in _PACKAGERS:
        return _PACKAGERS[packager_cls]
    p = packager_cls(**kwargs)
    _PACKAGERS[packager_cls] = p
    return p


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

    def patch(self, section):
        what_patches = self.get_option('patches', section)
        (_from_uri, target_dir) = self._get_download_location()
        if not what_patches:
            what_patches = []
        canon_what_patches = []
        for path in what_patches:
            if sh.isdir(path):
                canon_what_patches.extend(sorted(sh.listdir(path, files_only=True)))
            elif sh.isfile(path):
                canon_what_patches.append(path)
        if canon_what_patches:
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
            installer = make_packager(p, self.distro.package_manager_class,
                                      distro=self.distro)
            installer.pre_install(p, self.params)

    def post_install(self):
        pkgs = self.packages
        for p in pkgs:
            installer = make_packager(p, self.distro.package_manager_class,
                                      distro=self.distro)
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

    def _configure_symlinks(self):
        links = self.configurator.symlinks
        if not links:
            return 0
        # This sort happens so that we link in the correct order
        # although it might not matter. Either way. We ensure that the right
        # order happens. Ie /etc/blah link runs before /etc/blah/blah
        link_srcs = sorted(links.keys())
        link_srcs.reverse()
        link_nice = []
        for source in link_srcs:
            links_to_be = links[source]
            for link in links_to_be:
                link_nice.append("%s => %s" % (link, source))
        utils.log_iterable(link_nice, logger=LOG,
                           header="Creating %s sym-links" % (len(link_nice)))
        links_made = 0
        for source in link_srcs:
            links_to_be = links[source]
            for link in links_to_be:
                try:
                    LOG.debug("Symlinking %s to %s.", link, source)
                    sh.symlink(source, link, tracewriter=self.tracewriter)
                    links_made += 1
                except (IOError, OSError) as e:
                    LOG.warn("Symlinking %s to %s failed: %s", colorizer.quote(link), colorizer.quote(source), e)
        return links_made

    def prepare(self):
        pass

    def configure(self):
        return self._configure_files() + self._configure_symlinks()


class PythonInstallComponent(PkgInstallComponent):
    def __init__(self, *args, **kargs):
        PkgInstallComponent.__init__(self, *args, **kargs)
        tools_dir = sh.joinpths(self.get_option('app_dir'), 'tools')
        self.requires_files = [
            sh.joinpths(tools_dir, 'pip-requires'),
        ]
        if self.get_bool_option('use_tests_requires', default_value=True):
            self.requires_files.append(sh.joinpths(tools_dir, 'test-requires'))

    def _get_download_config(self):
        return 'get_from'


class PkgUninstallComponent(base.Component):
    def __init__(self, *args, **kargs):
        super(PkgUninstallComponent, self).__init__(*args, **kargs)
        trace_fn = tr.trace_filename(self.get_option('trace_dir'), 'created')
        self.tracereader = tr.TraceReader(trace_fn)
        self.purge_packages = kargs.get('purge_packages')

    def unconfigure(self):
        self._unconfigure_links()

    def _unconfigure_links(self):
        sym_files = self.tracereader.symlinks_made()
        if sym_files:
            utils.log_iterable(sym_files, logger=LOG,
                               header="Removing %s symlink files" % (len(sym_files)))
            for fn in sym_files:
                sh.unlink(fn, run_as_root=True)

    def post_uninstall(self):
        self._uninstall_files()
        self._uninstall_dirs()

    def pre_uninstall(self):
        pass

    def _uninstall_files(self):
        files_touched = self.tracereader.files_touched()
        if files_touched:
            utils.log_iterable(files_touched, logger=LOG,
                               header="Removing %s miscellaneous files" % (len(files_touched)))
            for fn in files_touched:
                sh.unlink(fn, run_as_root=True)

    def _uninstall_dirs(self):
        dirs_made = self.tracereader.dirs_made()
        dirs_alive = filter(sh.isdir, dirs_made)
        if dirs_alive:
            utils.log_iterable(dirs_alive, logger=LOG,
                               header="Removing %s created directories" % (len(dirs_alive)))
            for dir_name in dirs_alive:
                sh.deldir(dir_name, run_as_root=True)
