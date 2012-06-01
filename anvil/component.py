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

import re
import weakref

from anvil import colorizer
from anvil import downloader as down
from anvil import exceptions as excp
from anvil import importer
from anvil import log as logging
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils

LOG = logging.getLogger(__name__)

# Runtime status constants (return by runtime status)
# TODO: move...
STATUS_UNKNOWN = "unknown"
STATUS_STARTED = "started"
STATUS_STOPPED = "stopped"

# Progress bar titles
UNINSTALL_TITLE = 'Uninstalling'
INSTALL_TITLE = 'Installing'


class ComponentBase(object):
    def __init__(self,
                 desired_subsystems,
                 subsystem_info,
                 runner,
                 component_dir,
                 trace_dir,
                 app_dir,
                 cfg_dir,
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
        self.distro = runner.distro

        # Required component directories
        self.component_dir = component_dir
        self.trace_dir = trace_dir
        self.app_dir = app_dir
        self.cfg_dir = cfg_dir

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
            'APP_DIR': self.app_dir,
            'COMPONENT_DIR': self.component_dir,
            'CONFIG_DIR': self.cfg_dir,
            'TRACE_DIR': self.trace_dir,
        }

    def _get_trace_files(self):
        return {
            'install': tr.trace_fn(self.trace_dir, "install"),
            'start': tr.trace_fn(self.trace_dir, "start"),
        }

    def known_subsystems(self):
        return set()

    def known_options(self):
        return set()

    def warm_configs(self):
        pass

    def is_started(self):
        return tr.TraceReader(self._get_trace_files()['start']).exists()

    def is_installed(self):
        return tr.TraceReader(self._get_trace_files()['install']).exists()


class PkgInstallComponent(ComponentBase):
    def __init__(self, packager_factory, *args, **kargs):
        ComponentBase.__init__(self, *args, **kargs)
        self.tracewriter = tr.TraceWriter(self._get_trace_files()['install'], break_if_there=False)
        self.packages = kargs.get('packages', list())
        self.packager_factory = packager_factory

    def _get_download_locations(self):
        return list()

    def _get_real_download_locations(self):
        real_locations = list()
        for info in self._get_download_locations():
            section, key = info["uri"]
            uri = self.cfg.getdefaulted(section, key).strip()
            if not uri:
                raise ValueError(("Could not find uri in config to download "
                                   "from at section %s for option %s") % (section, key))
            target_directory = self.app_dir
            if 'subdir' in info:
                target_directory = sh.joinpths(target_directory, info["subdir"])
            branch = None
            if 'branch' in info:
                (section, key) = info['branch']
                branch = self.cfg.get(section, key)
            real_locations.append({
                'branch': branch,
                'target': target_directory,
                'uri': uri,
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
                LOG.debug("Extending package list with packages for subsystem %r", name)
                pkg_list.extend(self.subsystem_info[name].get('packages', []))
        return pkg_list

    def install(self):
        LOG.debug('Preparing to install packages for %r', self.component_name)
        pkgs = self._get_packages()
        if pkgs:
            pkg_names = [p['name'] for p in pkgs]
            utils.log_iterable(pkg_names, logger=LOG,
                header="Setting up %s distribution packages" % (len(pkg_names)))
            with utils.progress_bar(INSTALL_TITLE, len(pkgs)) as p_bar:
                for (i, p) in enumerate(pkgs):
                    self.tracewriter.package_installed(p)
                    self.packager_factory.get_packager_for(p).install(p)
                    p_bar.update(i + 1)
        return self.trace_dir

    def pre_install(self):
        pkgs = self._get_packages()
        for p in pkgs:
            self.packager_factory.get_packager_for(p).pre_install(p, self._get_param_map(None))

    def post_install(self):
        pkgs = self._get_packages()
        for p in pkgs:
            self.packager_factory.get_packager_for(p).post_install(p, self._get_param_map(None))

    def _get_config_files(self):
        return list()

    def _config_adjust(self, contents, config_fn):
        return contents

    def _get_target_config_name(self, config_fn):
        return sh.joinpths(self.cfg_dir, config_fn)

    def _get_source_config(self, config_fn):
        return utils.load_template(self.component_name, config_fn)

    def _get_link_dir(self):
        root_link_dir = self.distro.get_command_config('base_link_dir')
        return sh.joinpths(root_link_dir, self.component_name)

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
                LOG.info("Configuring file %s.", colorizer.quote(fn))
                (source_fn, contents) = self._get_source_config(fn)
                LOG.debug("Replacing parameters in file %r", source_fn)
                contents = self._config_param_replace(fn, contents, self._get_param_map(fn))
                LOG.debug("Applying final adjustments in file %r", source_fn)
                contents = self._config_adjust(contents, fn)
                LOG.info("Writing configuration file %s to %s.", colorizer.quote(source_fn), colorizer.quote(tgt_fn))
                self.tracewriter.cfg_file_written(sh.write_file(tgt_fn, contents))
        return len(config_fns)

    def _configure_symlinks(self):
        links = self._get_symlinks()
        # This sort happens so that we link in the correct order
        # although it might not matter. Either way. We ensure that the right
        # order happens. Ie /etc/blah link runs before /etc/blah/blah
        link_srcs = sorted(links.keys())
        link_srcs.reverse()
        links_made = 0
        for source in link_srcs:
            link = links.get(source)
            try:
                LOG.info("Symlinking %s to %s.", colorizer.quote(link), colorizer.quote(source))
                self.tracewriter.dirs_made(*sh.symlink(source, link))
                self.tracewriter.symlink_made(link)
                links_made += 1
            except OSError as e:
                LOG.warn("Symlinking %s to %s failed: %s", colorizer.quote(link), colorizer.quote(source), e)
        return links_made

    def configure(self):
        return self._configure_files() + self._configure_symlinks()


class PythonInstallComponent(PkgInstallComponent):
    def __init__(self, pip_factory, *args, **kargs):
        PkgInstallComponent.__init__(self, *args, **kargs)
        self.pips = kargs.get('pips', list())
        self.pip_factory = pip_factory

    def _get_python_directories(self):
        py_dirs = {
            self.component_name: self.app_dir,
        }
        return py_dirs

    def _get_pips(self):
        pip_list = list(self.pips)
        for name in self.desired_subsystems:
            if name in self.subsystem_info:
                LOG.debug("Extending pip list with pips for subsystem %r" % (name))
                subsystem_pips = self.subsystem_info[name].get('pips', list())
                pip_list.extend(subsystem_pips)
        return pip_list

    def _install_pips(self):
        pips = self._get_pips()
        if pips:
            pip_names = [p['name'] for p in pips]
            utils.log_iterable(pip_names, logger=LOG,
                header="Setting up %s python packages" % (len(pip_names)))
            with utils.progress_bar(INSTALL_TITLE, len(pips)) as p_bar:
                for (i, p) in enumerate(pips):
                    self.tracewriter.pip_installed(p)
                    self.pip_factory.get_packager_for(p).install(p)
                    p_bar.update(i + 1)

    def pre_install(self):
        PkgInstallComponent.pre_install(self)
        pips = self._get_pips()
        for p in pips:
            self.pip_factory.get_packager_for(p).pre_install(p, self._get_param_map(None))

    def post_install(self):
        PkgInstallComponent.post_install(self)
        pips = self._get_pips()
        for p in pips:
            self.pip_factory.get_packager_for(p).post_install(p, self._get_param_map(None))

    def _install_python_setups(self):
        py_dirs = self._get_python_directories()
        if py_dirs:
            real_dirs = dict()
            for (name, wkdir) in py_dirs.items():
                real_dirs[name] = wkdir or self.app_dir
            utils.log_iterable(real_dirs.values(), logger=LOG,
                header="Setting up %s python directories" % (len(real_dirs)))
            setup_cmd = self.distro.get_command('python', 'setup')
            for (name, working_dir) in real_dirs.items():
                self.tracewriter.dirs_made(*sh.mkdirslist(working_dir))
                self.tracewriter.py_installed(name, working_dir)
                (stdout, stderr) = sh.execute(*setup_cmd,
                                               cwd=working_dir,
                                               run_as_root=True)
                py_trace_name = "%s.%s" % (name, 'python')
                py_writer = tr.TraceWriter(tr.trace_fn(self.trace_dir,
                                                       py_trace_name), break_if_there=False)
                # Format or json encoding isn't really needed here since this is
                # more just for information output/lookup if desired.
                py_writer.trace("CMD", " ".join(setup_cmd))
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


class PkgUninstallComponent(ComponentBase):
    def __init__(self, packager_factory, *args, **kargs):
        ComponentBase.__init__(self, *args, **kargs)
        self.tracereader = tr.TraceReader(self._get_trace_files()['install'])
        self.keep_old = kargs.get('keep_old', False)
        self.packager_factory = packager_factory

    def unconfigure(self):
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
        LOG.debug("Deleting install trace file %r", self.tracereader.filename())
        sh.unlink(self.tracereader.filename())

    def post_uninstall(self):
        pass

    def pre_uninstall(self):
        pass

    def _uninstall_pkgs(self):
        if self.keep_old:
            LOG.info('Keep-old flag set, not removing any packages.')
        else:
            pkgs = self.tracereader.packages_installed()
            if pkgs:
                pkg_names = set([p['name'] for p in pkgs])
                utils.log_iterable(pkg_names, logger=LOG,
                    header="Potentially removing %s packages" % (len(pkg_names)))
                which_removed = set()
                with utils.progress_bar(UNINSTALL_TITLE, len(pkgs), reverse=True) as p_bar:
                    for (i, p) in enumerate(pkgs):
                        if self.packager_factory.get_packager_for(p).remove(p):
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
                    if sh.isdir(dir_name):
                        sh.deldir(dir_name, run_as_root=True)
                    else:
                        LOG.warn("No directory found at %s - skipping", colorizer.quote(dir_name, quote_color='red'))


class PythonUninstallComponent(PkgUninstallComponent):
    def __init__(self, pip_factory, *args, **kargs):
        PkgUninstallComponent.__init__(self, *args, **kargs)
        self.pip_factory = pip_factory

    def uninstall(self):
        self._uninstall_python()
        self._uninstall_pips()
        PkgUninstallComponent.uninstall(self)

    def _uninstall_pips(self):
        if self.keep_old:
            LOG.info('Keep-old flag set, not removing any python packages.')
        else:
            pips = self.tracereader.pips_installed()
            if pips:
                pip_names = set([p['name'] for p in pips])
                utils.log_iterable(pip_names, logger=LOG,
                    header="Uninstalling %s python packages" % (len(pip_names)))
                with utils.progress_bar(UNINSTALL_TITLE, len(pips), reverse=True) as p_bar:
                    for (i, p) in enumerate(pips):
                        try:
                            self.pip_factory.get_packager_for(p).remove(p)
                        except excp.ProcessExecutionError as e:
                            # NOTE(harlowja): pip seems to die if a pkg isn't there even in quiet mode
                            combined = (str(e.stderr) + str(e.stdout))
                            if not re.search(r"not\s+installed", combined, re.I):
                                raise
                        p_bar.update(i + 1)

    def _uninstall_python(self):
        py_listing = self.tracereader.py_listing()
        if py_listing:
            py_listing_dirs = set()
            for (name, where) in py_listing:
                py_listing_dirs.add(where)
            utils.log_iterable(py_listing_dirs, logger=LOG,
                header="Uninstalling %s python setups" % (len(py_listing_dirs)))
            unsetup_cmd = self.distro.get_command('python', 'unsetup')
            for where in py_listing_dirs:
                if sh.isdir(where):
                    sh.execute(*unsetup_cmd, cwd=where, run_as_root=True)
                else:
                    LOG.warn("No python directory found at %s - skipping", colorizer.quote(where, quote_color='red'))


class ProgramRuntime(ComponentBase):
    def __init__(self, *args, **kargs):
        ComponentBase.__init__(self, *args, **kargs)
        self.tracewriter = tr.TraceWriter(self._get_trace_files()['start'], break_if_there=True)
        self.tracereader = tr.TraceReader(self._get_trace_files()['start'])

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

    def post_stop(self, apps_started):
        pass

    def pre_stop(self, apps_started):
        pass

    def _fetch_run_type(self):
        return self.cfg.getdefaulted("DEFAULT", "run_type", 'anvil.runners.fork:ForkRunner')

    def configure(self):
        # Anything to configure for starting?
        apps_to_start = self._get_apps_to_start()
        am_configured = 0
        if not apps_to_start:
            return am_configured
        # First make a pass and make sure all runtime 
        # (e.g. upstart starting)
        # config files are in place....
        run_type = self._fetch_run_type()
        cls = importer.import_entry_point(run_type)
        instance = cls(self.cfg, self.component_name, self.trace_dir)
        for app_info in apps_to_start:
            app_name = app_info["name"]
            app_pth = app_info.get("path", app_name)
            app_dir = app_info.get("app_dir", self.app_dir)
            # Configure it with the given settings
            LOG.debug("Configuring runner %r for program %r", run_type, app_name)
            cfg_am = instance.configure(app_name,
                     app_pth=app_pth, app_dir=app_dir,
                     opts=utils.param_replace_list(self._get_app_options(app_name), self._get_param_map(app_name)))
            LOG.debug("Configured %s files for runner for program %r", cfg_am, app_name)
            am_configured += cfg_am
        return am_configured

    def start(self):
        # Anything to start?
        am_started = 0
        apps_to_start = self._get_apps_to_start()
        if not apps_to_start:
            return am_started
        # Select how we are going to start it
        run_type = self._fetch_run_type()
        cls = importer.import_entry_point(run_type)
        instance = cls(self.cfg, self.component_name, self.trace_dir)
        for app_info in apps_to_start:
            app_name = app_info["name"]
            app_pth = app_info.get("path", app_name)
            app_dir = app_info.get("app_dir", self.app_dir)
            # Adjust the program options now that we have real locations
            program_opts = utils.param_replace_list(self._get_app_options(app_name), self._get_param_map(app_name))
            # Start it with the given settings
            LOG.debug("Starting %r using %r", app_name, run_type)
            details_fn = instance.start(app_name,
                app_pth=app_pth, app_dir=app_dir, opts=program_opts)
            LOG.info("Started %s details are in %s", colorizer.quote(app_name), colorizer.quote(details_fn))
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
                LOG.warn("Could not load class %s which should be used to stop %s: %s", 
                         colorizer.quote(how), colorizer.quote(app_name), e)
                continue
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
        # Anything to stop??
        killed_am = 0
        apps_started = self.tracereader.apps_started()
        if not apps_started:
            return killed_am
        self.pre_stop(apps_started)
        to_kill = self._locate_killers(apps_started)
        for (app_name, killer) in to_kill:
            killer.stop(app_name)
            killer.unconfigure()
            killed_am += 1
        self.post_stop(apps_started)
        if len(apps_started) == killed_am:
            sh.unlink(self.tracereader.filename())
        return killed_am

    def status(self):
        return STATUS_UNKNOWN

    def restart(self):
        return 0


class PythonRuntime(ProgramRuntime):
    def __init__(self, *args, **kargs):
        ProgramRuntime.__init__(self, *args, **kargs)


class EmptyRuntime(ProgramRuntime):
    def __init__(self, *args, **kargs):
        ProgramRuntime.__init__(self, *args, **kargs)
