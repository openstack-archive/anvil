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

import weakref

from devstack import downloader as down
from devstack import importer
from devstack import log as logging
from devstack import pip
from devstack import settings
from devstack import shell as sh
from devstack import trace as tr
from devstack import utils

LOG = logging.getLogger("devstack.component")

# How we actually setup and unsetup python
PY_INSTALL = ['python', 'setup.py', 'develop']
PY_UNINSTALL = ['python', 'setup.py', 'develop', '--uninstall']

# Runtime status constants (return by runtime status)
# TODO: move...
STATUS_UNKNOWN = "unknown"
STATUS_STARTED = "started"
STATUS_STOPPED = "stopped"

# Where symlinks will go
BASE_LINK_DIR = "/etc"

# Progress bar titles
UNINSTALL_TITLE = 'Uninstalling'
INSTALL_TITLE = 'Installing'


class ComponentBase(object):
    def __init__(self,
                 desired_subsystems,
                 subsystem_info,
                 runner,
                 component_dir,
                 all_instances,
                 options,
                 name,
                 *args,
                 **kargs):

        self.desired_subsystems = desired_subsystems
        self.instances = all_instances
        self.component_name = name
        self.subsystem_info = subsystem_info
        self.options = options

        # The runner has a reference to us, so use a weakref here to
        # avoid breaking garbage collection.
        self.runner = weakref.proxy(runner)

        # Parts of the global runner context that we use
        self.cfg = runner.cfg
        self.pw_gen = runner.pw_gen
        self.distro = runner.distro

        # Required component directories
        self.component_dir = component_dir
        self.trace_dir = sh.joinpths(self.component_dir,
                                    settings.COMPONENT_TRACE_DIR)
        self.app_dir = sh.joinpths(self.component_dir,
                                  settings.COMPONENT_APP_DIR)
        self.cfg_dir = sh.joinpths(self.component_dir,
                                  settings.COMPONENT_CONFIG_DIR)

    def verify(self):
        # Ensure subsystems are known...
        knowns = self.known_subsystems()
        for s in self.desired_subsystems:
            if s not in knowns:
                raise ValueError("Unknown subsystem %r requested for (%s)" % (s, self))
        for s in self.subsystem_info.keys():
            if s not in knowns:
                raise ValueError("Unknown subsystem %r provided for (%s)" % (s, self))
        known_options = self.known_options()
        for s in self.options:
            if s not in known_options:
                LOG.warning("Unknown option %r provided for (%s)" % (s, self))

    def __str__(self):
        return "%s: %s" % (self.__class__.__name__, self.component_name)

    def _get_params(self):
        return {
            'COMPONENT_DIR': self.component_dir,
            'APP_DIR': self.app_dir,
            'CONFIG_DIR': self.cfg_dir,
            'TRACE_DIR': self.trace_dir,
        }

    def known_subsystems(self):
        return set()

    def known_options(self):
        return set()

    def warm_configs(self):
        pass

    def is_started(self):
        return tr.TraceReader(tr.trace_fn(self.trace_dir, tr.START_TRACE)).exists()

    def is_installed(self):
        return tr.TraceReader(tr.trace_fn(self.trace_dir, tr.IN_TRACE)).exists()


class PackageBasedComponentMixin(object):
    """Mix this into classes that need to manipulate
    OS-level packages.
    """
    PACKAGER_KEY_NAME = 'packager_name'

    def __init__(self):
        self.default_packager = self.distro.get_default_package_manager()

    def get_packager(self, pkg_info):
        if self.PACKAGER_KEY_NAME in pkg_info:
            packager_name = pkg_info[self.PACKAGER_KEY_NAME]
            LOG.debug('Loading custom package manager %r', packager_name)
            packager = importer.import_entry_point(packager_name)(self.distro)
        else:
            LOG.debug('Using default package manager')
            packager = self.default_packager
        return packager


class PkgInstallComponent(ComponentBase, PackageBasedComponentMixin):
    def __init__(self, *args, **kargs):
        ComponentBase.__init__(self, *args, **kargs)
        PackageBasedComponentMixin.__init__(self)
        self.tracewriter = tr.TraceWriter(tr.trace_fn(self.trace_dir,
                                                      tr.IN_TRACE))
        self.packages = kargs.get('packages', list())

    def _get_download_locations(self):
        return list()

    def _get_real_download_locations(self):
        real_locations = list()
        for info in self._get_download_locations():
            section, key = info["uri"]
            uri = self.cfg.get(section, key)
            target_directory = self.app_dir
            if 'subdir' in info:
                target_directory = sh.joinpths(target_directory, info["subdir"])
            branch = None
            if 'branch' in info:
                section, key = info['branch']
                branch = self.cfg.get(section, key)
            real_locations.append({
                'uri': uri,
                'target': target_directory,
                'branch': branch,
            })
        return real_locations

    def download(self):
        download_locs = self._get_real_download_locations()
        uris = [loc['uri'] for loc in download_locs]
        utils.log_iterable(uris, logger=LOG,
                header="Downloading from %s uris" % (len(uris)))
        for info in download_locs:
            # Extract da download!
            uri = info['uri']
            target_loc = info['target']
            branch = info['branch']
            # Activate da download!
            self.tracewriter.download_happened(target_loc, uri)
            dirs_made = self._do_download(uri, target_loc, branch)
            # Here we ensure this is always added so that
            # if a keep old happens then this of course
            # won't be recreated, but if u uninstall without keeping old
            # then this won't be deleted this time around
            # adding it in is harmless and will make sure its removed.
            if target_loc not in dirs_made:
                dirs_made.append(target_loc)
            self.tracewriter.dirs_made(*dirs_made)
        return len(download_locs)

    def _do_download(self, uri, target_dir, branch):
        return down.GitDownloader(self.distro, uri, target_dir, branch).download()

    def _get_param_map(self, config_fn):
        mp = ComponentBase._get_params(self)
        mp['CONFIG_FN'] = config_fn or ''
        return mp

    def _get_packages(self):
        pkg_list = list(self.packages)
        for name in self.desired_subsystems:
            if name in self.subsystem_info:
                # Todo handle duplicates/version differences?
                LOG.debug(
                    "Extending package list with packages for subsystem %r",
                    name)
                subsystem_pkgs = self.subsystem_info[name].get('packages', [])
                pkg_list.extend(subsystem_pkgs)
        return pkg_list

    def install(self):
        LOG.debug('Preparing to install packages for %r', self.component_name)
        pkgs = self._get_packages()
        if pkgs:
            pkg_names = set([p['name'] for p in pkgs])
            utils.log_iterable(pkg_names, logger=LOG,
                header="Setting up %s distribution packages" % (len(pkg_names)))
            with utils.progress_bar(INSTALL_TITLE, len(pkgs)) as p_bar:
                for (i, p) in enumerate(pkgs):
                    self.tracewriter.package_installed(p)
                    packager = self.get_packager(p)
                    packager.install(p)
                    p_bar.update(i + 1)
        else:
            LOG.info('No packages to install for %r', self.component_name)
        return self.trace_dir

    def pre_install(self):
        pkgs = self._get_packages()
        if pkgs:
            mp = self._get_param_map(None)
            for p in pkgs:
                packager = self.get_packager(p)
                packager.pre_install(p, mp)

    def post_install(self):
        pkgs = self._get_packages()
        if pkgs:
            mp = self._get_param_map(None)
            for p in pkgs:
                packager = self.get_packager(p)
                packager.post_install(p, mp)

    def _get_config_files(self):
        return list()

    def _config_adjust(self, contents, config_fn):
        return contents

    def _get_target_config_name(self, config_fn):
        return sh.joinpths(self.cfg_dir, config_fn)

    def _get_source_config(self, config_fn):
        return utils.load_template(self.component_name, config_fn)

    def _get_link_dir(self):
        return sh.joinpths(BASE_LINK_DIR, self.component_name)

    def _get_symlinks(self):
        links = dict()
        for fn in self._get_config_files():
            source_fn = self._get_target_config_name(fn)
            links[source_fn] = sh.joinpths(self._get_link_dir(), fn)
        return links

    def _config_param_replace(self, config_fn, contents, parameters):
        return utils.param_replace(contents, parameters)

    def _configure_files(self):
        config_fns = self._get_config_files()
        if config_fns:
            utils.log_iterable(config_fns, logger=LOG,
                header="Configuring %s files" % (len(config_fns)))
            for fn in config_fns:
                tgt_fn = self._get_target_config_name(fn)
                self.tracewriter.dirs_made(*sh.mkdirslist(sh.dirname(tgt_fn)))
                LOG.info("Configuring file %r", fn)
                (source_fn, contents) = self._get_source_config(fn)
                LOG.debug("Replacing parameters in file %r", source_fn)
                contents = self._config_param_replace(fn, contents, self._get_param_map(fn))
                LOG.debug("Applying final adjustments in file %r", source_fn)
                contents = self._config_adjust(contents, fn)
                LOG.info("Writing configuration file %r => %r", source_fn, tgt_fn)
                self.tracewriter.cfg_file_written(sh.write_file(tgt_fn, contents))
        return len(config_fns)

    def _configure_symlinks(self):
        links = self._get_symlinks()
        # This sort happens so that we link in the correct order
        # although it might not matter. Either way. We ensure that the right
        # order happens. Ie /etc/blah link runs before /etc/blah/blah
        link_srcs = sorted(links.keys())
        link_srcs.reverse()
        for source in link_srcs:
            link = links.get(source)
            try:
                LOG.info("Symlinking %r => %r", link, source)
                self.tracewriter.dirs_made(*sh.symlink(source, link))
                self.tracewriter.symlink_made(link)
            except OSError as e:
                LOG.warn("Symlink (%r => %r) error (%s)", link, source, e)
        return len(links)

    def configure(self):
        return self._configure_files() + self._configure_symlinks()


class PythonInstallComponent(PkgInstallComponent):
    def __init__(self, *args, **kargs):
        PkgInstallComponent.__init__(self, *args, **kargs)
        self.pips = kargs.get('pips', list())

    def _get_python_directories(self):
        py_dirs = dict()
        py_dirs[self.component_name] = self.app_dir
        return py_dirs

    def _get_pips(self):
        pip_list = list(self.pips)
        for name in self.desired_subsystems:
            if name in self.subsystem_info:
                # TODO handle duplicates/version differences?
                LOG.debug("Extending pip list with pips for subsystem %r" % (name))
                subsystem_pips = self.subsystem_info[name].get('pips', list())
                pip_list.extend(subsystem_pips)
        return pip_list

    def _install_pips(self):
        pips = self._get_pips()
        if pips:
            pip_names = set([p['name'] for p in pips])
            utils.log_iterable(pip_names, logger=LOG,
                header="Setting up %s python packages" % (len(pip_names)))
            with utils.progress_bar(INSTALL_TITLE, len(pips)) as p_bar:
                for (i, p) in enumerate(pips):
                    self.tracewriter.pip_installed(p)
                    pip.install(p, self.distro)
                    p_bar.update(i + 1)

    def _install_python_setups(self):
        py_dirs = self._get_python_directories()
        if py_dirs:
            real_dirs = dict()
            for (name, wkdir) in py_dirs.items():
                real_dirs[name] = wkdir or self.app_dir
            utils.log_iterable(real_dirs.values(), logger=LOG,
                header="Setting up %s python directories" % (len(real_dirs)))
            for (name, working_dir) in real_dirs.items():
                self.tracewriter.dirs_made(*sh.mkdirslist(working_dir))
                self.tracewriter.py_installed(name, working_dir)
                (stdout, stderr) = sh.execute(*PY_INSTALL,
                                               cwd=working_dir,
                                               run_as_root=True)
                py_trace_name = "%s-%s" % (tr.PY_TRACE, name)
                py_writer = tr.TraceWriter(tr.trace_fn(self.trace_dir,
                                                       py_trace_name))
                # Format or json encoding isn't really needed here since this is
                # more just for information output/lookup if desired.
                py_writer.trace("CMD", " ".join(PY_INSTALL))
                py_writer.trace("STDOUT", stdout)
                py_writer.trace("STDERR", stderr)
                self.tracewriter.file_touched(py_writer.filename())

    def _python_install(self):
        self._install_pips()
        self._install_python_setups()

    def install(self):
        trace_dir = PkgInstallComponent.install(self)
        self._python_install()
        return trace_dir


class PkgUninstallComponent(ComponentBase, PackageBasedComponentMixin):
    def __init__(self, *args, **kargs):
        ComponentBase.__init__(self, *args, **kargs)
        PackageBasedComponentMixin.__init__(self)
        self.tracereader = tr.TraceReader(tr.trace_fn(self.trace_dir,
                                                      tr.IN_TRACE))
        self.keep_old = kargs.get('keep_old')

    def unconfigure(self):
        if not self.keep_old:
            # TODO this may not be the best solution siance we might
            # actually want to remove config files but since most
            # config files can be regenerated this should be fine (some
            # can not though) so this is why we need to keep them.
            self._unconfigure_files()
        self._unconfigure_links()

    def _unconfigure_links(self):
        sym_files = self.tracereader.symlinks_made()
        if sym_files:
            utils.log_iterable(sym_files, logger=LOG,
                header="Removing %s symlink files" % (len(sym_files)))
            for fn in sym_files:
                sh.unlink(fn, run_as_root=True)

    def _unconfigure_files(self):
        cfg_files = self.tracereader.files_configured()
        if cfg_files:
            utils.log_iterable(cfg_files, logger=LOG,
                header="Removing %s configuration files" % (len(cfg_files)))
            for fn in cfg_files:
                sh.unlink(fn, run_as_root=True)

    def uninstall(self):
        self._uninstall_pkgs()
        self._uninstall_touched_files()
        self._uninstall_dirs()

    def post_uninstall(self):
        pass

    def pre_uninstall(self):
        pass

    def _uninstall_pkgs(self):
        if self.keep_old:
            LOG.info('Keep-old flag set, not removing any packages.')
            return
        pkgs = self.tracereader.packages_installed()
        if pkgs:
            pkg_names = set([p['name'] for p in pkgs])
            utils.log_iterable(pkg_names, logger=LOG,
                header="Potentially removing %s packages" % (len(pkg_names)))
            which_removed = set()
            with utils.progress_bar(UNINSTALL_TITLE, len(pkgs), reverse=True) as p_bar:
                for (i, p) in enumerate(pkgs):
                    packager = self.get_packager(p)
                    if packager.remove(p):
                        which_removed.add(p['name'])
                    p_bar.update(i + 1)
            utils.log_iterable(which_removed, logger=LOG,
                header="Actually removed %s packages" % (len(which_removed)))

    def _uninstall_touched_files(self):
        files_touched = self.tracereader.files_touched()
        if files_touched:
            utils.log_iterable(files_touched, logger=LOG,
                header="Removing %s touched files" % (len(files_touched)))
            for fn in files_touched:
                sh.unlink(fn, run_as_root=True)

    def _uninstall_dirs(self):
        dirs_made = self.tracereader.dirs_made()
        if dirs_made:
            dirs_made = [sh.abspth(d) for d in dirs_made]
            if self.keep_old:
                download_places = [path_location[0] for path_location in self.tracereader.download_locations()]
                if download_places:
                    utils.log_iterable(download_places, logger=LOG,
                        header="Keeping %s download directories (and there children directories)" % (len(download_places)))
                    for download_place in download_places:
                        dirs_made = sh.remove_parents(download_place, dirs_made)
            if dirs_made:
                utils.log_iterable(dirs_made, logger=LOG,
                    header="Removing %s created directories" % (len(dirs_made)))
                for dir_name in dirs_made:
                    sh.deldir(dir_name, run_as_root=True)


class PythonUninstallComponent(PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        PkgUninstallComponent.__init__(self, *args, **kargs)

    def uninstall(self):
        self._uninstall_python()
        self._uninstall_pips()
        PkgUninstallComponent.uninstall(self)

    def _uninstall_pips(self):
        if self.keep_old:
            LOG.info('Keep-old flag set, not removing any python packages.')
            return
        pips = self.tracereader.pips_installed()
        if pips:
            pip_names = set([p['name'] for p in pips])
            utils.log_iterable(pip_names, logger=LOG,
                header="Uninstalling %s python packages" % (len(pip_names)))
            with utils.progress_bar(UNINSTALL_TITLE, len(pips), reverse=True) as p_bar:
                for (i, p) in enumerate(pips):
                    pip.uninstall(p, self.distro)
                    p_bar.update(i + 1)

    def _uninstall_python(self):
        py_listing = self.tracereader.py_listing()
        if py_listing:
            py_listing_dirs = set()
            for (_, where) in py_listing:
                py_listing_dirs.add(where)
            utils.log_iterable(py_listing_dirs, logger=LOG,
                header="Uninstalling %s python setups" % (len(py_listing_dirs)))
            for where in py_listing_dirs:
                sh.execute(*PY_UNINSTALL, cwd=where, run_as_root=True)


class ProgramRuntime(ComponentBase):
    def __init__(self, *args, **kargs):
        ComponentBase.__init__(self, *args, **kargs)
        self.tracewriter = tr.TraceWriter(tr.trace_fn(self.trace_dir, tr.START_TRACE))
        self.tracereader = tr.TraceReader(tr.trace_fn(self.trace_dir, tr.START_TRACE))

    def _get_apps_to_start(self):
        return list()

    def _get_app_options(self, app_name):
        return list()

    def _get_param_map(self, app_name):
        mp = ComponentBase._get_params(self)
        mp['APP_NAME'] = app_name or ''
        return mp

    def pre_start(self):
        pass

    def post_start(self):
        pass

    def _fetch_run_type(self):
        return self.cfg.getdefaulted("DEFAULT", "run_type", 'devstack.runners.fork:ForkRunner')

    def configure(self):
        # First make a pass and make sure all runtime (e.g. upstart starting)
        # config files are in place....
        run_type = self._fetch_run_type()
        cls = importer.import_entry_point(run_type)
        instance = cls(self.cfg, self.component_name, self.trace_dir)
        tot_am = 0
        for app_info in self._get_apps_to_start():
            app_name = app_info["name"]
            app_pth = app_info.get("path", app_name)
            app_dir = app_info.get("app_dir", self.app_dir)
            # Configure it with the given settings
            LOG.debug("Configuring runner %r for program %r", run_type, app_name)
            cfg_am = instance.configure(app_name,
                     app_pth=app_pth, app_dir=app_dir,
                     opts=utils.param_replace_list(self._get_app_options(app_name), self._get_param_map(app_name)))
            LOG.debug("Configured %s files for runner for program %r", cfg_am, app_name)
            tot_am += cfg_am
        return tot_am

    def start(self):
        # Select how we are going to start it
        run_type = self._fetch_run_type()
        cls = importer.import_entry_point(run_type)
        instance = cls(self.cfg, self.component_name, self.trace_dir)
        am_started = 0
        for app_info in self._get_apps_to_start():
            app_name = app_info["name"]
            app_pth = app_info.get("path", app_name)
            app_dir = app_info.get("app_dir", self.app_dir)
            # Adjust the program options now that we have real locations
            program_opts = utils.param_replace_list(self._get_app_options(app_name), self._get_param_map(app_name))
            # Start it with the given settings
            LOG.debug("Starting %r using %r", app_name, run_type)
            details_fn = instance.start(app_name,
                app_pth=app_pth, app_dir=app_dir, opts=program_opts)
            LOG.info("Started %r details are in %r", app_name, details_fn)
            # This trace is used to locate details about what to stop
            self.tracewriter.app_started(app_name, details_fn, run_type)
            am_started += 1
        return am_started

    def _locate_killers(self, apps_started):
        killer_instances = dict()
        to_kill = list()
        for (app_name, trace_fn, how) in apps_started:
            killcls = None
            try:
                killcls = importer.import_entry_point(how)
                LOG.debug("Stopping %r using %r", app_name, how)
            except RuntimeError as e:
                LOG.warn("Could not load class %r which should be used to stop %r: %s", how, app_name, e)
            if killcls in killer_instances:
                killer = killer_instances[killcls]
            else:
                killer = killcls(self.cfg,
                                 self.component_name,
                                 self.trace_dir)
                killer_instances[killcls] = killer
            to_kill.append((app_name, killer))
        return to_kill

    def stop(self):
        apps_started = self.tracereader.apps_started()
        to_kill = self._locate_killers(apps_started)
        for (app_name, killer) in to_kill:
            killer.stop(app_name)
        if len(apps_started) == len(to_kill):
            LOG.debug("Deleting start trace file %r", self.tracereader.filename())
            sh.unlink(self.tracereader.filename())
            for (app_name, killer) in to_kill:
                LOG.debug("Unconfiguring %r after successful stopping", app_name)
                killer.unconfigure()
        return len(to_kill)

    def status(self):
        return STATUS_UNKNOWN

    def restart(self):
        return 0


class PythonRuntime(ProgramRuntime):
    def __init__(self, *args, **kargs):
        ProgramRuntime.__init__(self, *args, **kargs)


class EmptyRuntime(ComponentBase):
    def __init__(self, *args, **kargs):
        ComponentBase.__init__(self, *args, **kargs)
        self.tracereader = tr.TraceReader(tr.trace_fn(self.trace_dir, tr.IN_TRACE))

    def configure(self):
        return 0

    def pre_start(self):
        pass

    def post_start(self):
        pass

    def start(self):
        return 0

    def stop(self):
        return 0

    def status(self):
        return STATUS_UNKNOWN

    def restart(self):
        return 0
