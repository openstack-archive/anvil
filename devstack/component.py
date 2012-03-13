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

from devstack import cfg
from devstack import downloader as down
from devstack import exceptions as excp
from devstack import log as logging
from devstack import pip
from devstack import settings
from devstack import shell as sh
from devstack import trace as tr
from devstack import utils

from devstack.runners import fork
from devstack.runners import upstart
from devstack.runners import screen

LOG = logging.getLogger("devstack.component")

#how we actually setup and unsetup python
PY_INSTALL = ['python', 'setup.py', 'develop']
PY_UNINSTALL = ['python', 'setup.py', 'develop', '--uninstall']

#runtime status constants (return by runtime status)
STATUS_UNKNOWN = "unknown"
STATUS_STARTED = "started"
STATUS_STOPPED = "stopped"

#which run types to which runner class
RUNNER_CLS_MAPPING = {
    settings.RUN_TYPE_FORK: fork.ForkRunner,
    settings.RUN_TYPE_UPSTART: upstart.UpstartRunner,
    settings.RUN_TYPE_SCREEN: screen.ScreenRunner,
}

#where symlinks will go
BASE_LINK_DIR = "/etc"


class ComponentBase(object):
    def __init__(self, component_name, runner, root, opts, instances=None,
                 **kwds):
        self.component_name = component_name
        # The runner has a reference to us, so use a weakref here to
        # avoid breaking garbage collection.
        self.runner = weakref.proxy(runner)
        self.root = root
        self.component_opts = opts or []
        self.instances = instances or {}

        # Parts of the global runner context that we use
        self.cfg = runner.cfg
        self.password_generator = runner.password_generator
        self.packager = runner.pkg_manager
        self.distro = runner.distro

        self.component_root = sh.joinpths(self.root, component_name)
        self.tracedir = sh.joinpths(self.component_root,
                                    settings.COMPONENT_TRACE_DIR)
        self.appdir = sh.joinpths(self.component_root,
                                  settings.COMPONENT_APP_DIR)
        self.cfgdir = sh.joinpths(self.component_root,
                                  settings.COMPONENT_CONFIG_DIR)
        self.kargs = kwds

    def get_dependencies(self):
        deps = settings.COMPONENT_DEPENDENCIES.get(self.component_name)
        if not deps:
            return list()
        return list(deps)

    def verify(self):
        pass

    def warm_configs(self):
        pass

    def is_started(self):
        return tr.TraceReader(tr.trace_fn(self.tracedir, tr.START_TRACE)).exists()

    def is_installed(self):
        return tr.TraceReader(tr.trace_fn(self.tracedir, tr.IN_TRACE)).exists()


class PkgInstallComponent(ComponentBase):
    def __init__(self, component_name, *args, **kargs):
        ComponentBase.__init__(self, component_name, *args, **kargs)
        self.tracewriter = tr.TraceWriter(tr.trace_fn(self.tracedir, tr.IN_TRACE))

    def _get_download_locations(self):
        return list()

    def download(self):
        locations = self._get_download_locations()
        base_dir = self.appdir
        for location_info in locations:
            uri_tuple = location_info["uri"]
            branch_tuple = location_info.get("branch")
            subdir = location_info.get("subdir")
            target_loc = base_dir
            if subdir:
                target_loc = sh.joinpths(base_dir, subdir)
            branch = None
            if branch_tuple:
                (cfg_section, cfg_key) = branch_tuple
                branch = self.cfg.get(cfg_section, cfg_key)
                if not branch:
                    msg = "No branch entry found at config location [%s]" % (cfg.make_id(cfg_section, cfg_key))
                    raise excp.ConfigException(msg)
            (cfg_section, cfg_key) = uri_tuple
            uri = self.cfg.get(cfg_section, cfg_key)
            if not uri:
                msg = "No uri entry found at config location [%s]" % (cfg.make_id(cfg_section, cfg_key))
                raise excp.ConfigException(msg)
            self.tracewriter.download_happened(target_loc, uri)
            dirs_made = down.download(target_loc, uri, branch)
            #ensure this is always added so that
            #if a keep old happens then this of course
            #won't be recreated, but if u uninstall without keeping old
            #then this won't be deleted this time around
            #adding it in is harmless and willl make sure its removed
            dirs_made.append(target_loc)
            self.tracewriter.dirs_made(*dirs_made)
        return len(locations)

    def _get_param_map(self, config_fn):
        return dict()

    def _get_pkgs(self):
        return list()

    def _get_pkgs_expanded(self):
        short = self._get_pkgs()
        if not short:
            return dict()
        pkgs = dict()
        for fn in short:
            full_name = sh.joinpths(settings.STACK_PKG_DIR, fn)
            pkgs = utils.extract_pkg_list([full_name], self.distro, pkgs)
        return pkgs

    def install(self):
        pkgs = self._get_pkgs_expanded()
        if pkgs:
            pkgnames = sorted(pkgs.keys())
            LOG.info("Installing packages (%s)." % (", ".join(pkgnames)))
            #do this before install just incase it craps out half way through
            for name in pkgnames:
                self.tracewriter.package_installed(name, pkgs.get(name))
            #now actually install
            self.packager.install_batch(pkgs)
        return self.tracedir

    def pre_install(self):
        pkgs = self._get_pkgs_expanded()
        if pkgs:
            mp = self._get_param_map(None)
            self.packager.pre_install(pkgs, mp)

    def post_install(self):
        pkgs = self._get_pkgs_expanded()
        if pkgs:
            mp = self._get_param_map(None)
            self.packager.post_install(pkgs, mp)

    def _get_config_files(self):
        return list()

    def _config_adjust(self, contents, config_fn):
        return contents

    def _get_target_config_name(self, config_fn):
        return sh.joinpths(self.cfgdir, config_fn)

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

    def _configure_files(self):
        configs = self._get_config_files()
        if configs:
            LOG.info("Configuring %s files" % (len(configs)))
            for fn in configs:
                #get the params and where it should come from and where it should go
                parameters = self._get_param_map(fn)
                tgt_fn = self._get_target_config_name(fn)
                #ensure directory is there (if not created previously)
                self.tracewriter.dirs_made(*sh.mkdirslist(sh.dirname(tgt_fn)))
                #now configure it
                LOG.info("Configuring file %s" % (fn))
                (source_fn, contents) = self._get_source_config(fn)
                LOG.debug("Replacing parameters in file %s" % (source_fn))
                LOG.debug("Replacements = %s" % (parameters))
                contents = utils.param_replace(contents, parameters)
                LOG.debug("Applying side-effects of param replacement for template %s" % (source_fn))
                contents = self._config_adjust(contents, fn)
                LOG.info("Writing configuration file %s" % (tgt_fn))
                #this trace is used to remove the files configured
                self.tracewriter.cfg_file_written(sh.write_file(tgt_fn, contents))
        return len(configs)

    def _configure_symlinks(self):
        links = self._get_symlinks()
        link_srcs = sorted(links.keys())
        link_srcs.reverse()
        for source in link_srcs:
            link = links.get(source)
            try:
                LOG.info("Symlinking %s => %s" % (link, source))
                self.tracewriter.dirs_made(*sh.symlink(source, link))
                self.tracewriter.symlink_made(link)
            except OSError:
                LOG.warn("Symlink %s => %s already exists." % (link, source))
        return len(links)

    def configure(self):
        conf_am = self._configure_files()
        conf_am += self._configure_symlinks()
        return conf_am


class PythonInstallComponent(PkgInstallComponent):
    def __init__(self, component_name, *args, **kargs):
        PkgInstallComponent.__init__(self, component_name, *args, **kargs)

    def _get_python_directories(self):
        py_dirs = dict()
        py_dirs[self.component_name] = self.appdir
        return py_dirs

    def _get_pips(self):
        return list()

    def _get_pips_expanded(self):
        shorts = self._get_pips()
        if not shorts:
            return dict()
        pips = dict()
        for fn in shorts:
            full_name = sh.joinpths(settings.STACK_PIP_DIR, fn)
            pips = utils.extract_pip_list([full_name], self.distro, pips)
        return pips

    def _install_pips(self):
        pips = self._get_pips_expanded()
        if pips:
            LOG.info("Setting up %s pips (%s)" % (len(pips), ", ".join(pips.keys())))
            #do this before install just incase it craps out half way through
            for name in pips.keys():
                self.tracewriter.pip_installed(name, pips.get(name))
            #now install
            pip.install(pips, self.distro)

    def _install_python_setups(self):
        pydirs = self._get_python_directories()
        if pydirs:
            LOG.info("Setting up %s python directories (%s)" % (len(pydirs), pydirs))
            for (name, wkdir) in pydirs.items():
                working_dir = wkdir or self.appdir
                #ensure working dir is there
                self.tracewriter.dirs_made(*sh.mkdirslist(working_dir))
                #do this before write just incase it craps out half way through
                self.tracewriter.py_installed(name, working_dir)
                #now actually do it
                (stdout, stderr) = sh.execute(*PY_INSTALL, cwd=working_dir, run_as_root=True)
                py_trace_name = "%s-%s" % (tr.PY_TRACE, name)
                py_writer = tr.TraceWriter(tr.trace_fn(self.tracedir, py_trace_name))
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


class PkgUninstallComponent(ComponentBase):
    def __init__(self, component_name, *args, **kargs):
        ComponentBase.__init__(self, component_name, *args, **kargs)
        self.tracereader = tr.TraceReader(tr.trace_fn(self.tracedir, tr.IN_TRACE))
        self.keep_old = kargs.get("keep_old")

    def unconfigure(self):
        if not self.keep_old:
            #TODO this may not be the best solution since we might actually want to remove config files
            #but since most config files can be regenerated this should be fine (some can not though)
            #so this is why we need to keep them
            self._unconfigure_files()
        self._unconfigure_links()
        self._unconfigure_runners()

    def _unconfigure_runners(self):
        if RUNNER_CLS_MAPPING:
            LOG.info("Unconfiguring %s runners." % (len(RUNNER_CLS_MAPPING)))
            for (_, cls) in RUNNER_CLS_MAPPING.items():
                instance = cls(self.cfg, self.component_name, self.tracedir)
                instance.unconfigure()

    def _unconfigure_links(self):
        symfiles = self.tracereader.symlinks_made()
        if symfiles:
            LOG.info("Removing %s symlink files (%s)" % (len(symfiles), ", ".join(symfiles)))
            for fn in symfiles:
                sh.unlink(fn, run_as_root=True)

    def _unconfigure_files(self):
        cfgfiles = self.tracereader.files_configured()
        if cfgfiles:
            LOG.info("Removing %s configuration files (%s)" % (len(cfgfiles), ", ".join(cfgfiles)))
            for fn in cfgfiles:
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
        pkgsfull = self.tracereader.packages_installed()
        if pkgsfull:
            LOG.info("Potentially removing %s packages (%s)" % (len(pkgsfull), ", ".join(sorted(pkgsfull.keys()))))
            which_removed = self.packager.remove_batch(pkgsfull)
            LOG.info("Actually removed %s packages (%s)" % (len(which_removed), ", ".join(sorted(which_removed))))

    def _uninstall_touched_files(self):
        filestouched = self.tracereader.files_touched()
        if filestouched:
            LOG.info("Removing %s touched files (%s)" % (len(filestouched), ", ".join(filestouched)))
            for fn in filestouched:
                sh.unlink(fn, run_as_root=True)

    def _uninstall_dirs(self):
        dirsmade = self.tracereader.dirs_made()
        if dirsmade:
            dirsmade = [sh.abspth(d) for d in dirsmade]
            if self.keep_old:
                places = set()
                for (pth_loc, _) in self.tracereader.download_locations():
                    places.add(pth_loc)
                LOG.info("Keeping %s download directories [%s]" % (len(places), ",".join(sorted(places))))
                for download_place in places:
                    dirsmade = sh.remove_parents(download_place, dirsmade)
            for dirname in dirsmade:
                LOG.info("Removing created directory (%s)" % (dirname))
                sh.deldir(dirname, run_as_root=True)


class PythonUninstallComponent(PkgUninstallComponent):
    def __init__(self, component_name, *args, **kargs):
        PkgUninstallComponent.__init__(self, component_name, *args, **kargs)

    def uninstall(self):
        self._uninstall_python()
        self._uninstall_pips()
        PkgUninstallComponent.uninstall(self)

    def _uninstall_pips(self):
        pips = self.tracereader.pips_installed()
        if pips:
            LOG.info("Uninstalling %s pips." % (len(pips)))
            pip.uninstall(pips, self.distro)

    def _uninstall_python(self):
        pylisting = self.tracereader.py_listing()
        if pylisting:
            LOG.info("Uninstalling %s python setups." % (len(pylisting)))
            for (_, where) in pylisting:
                sh.execute(*PY_UNINSTALL, cwd=where, run_as_root=True)


class ProgramRuntime(ComponentBase):
    def __init__(self, component_name, *args, **kargs):
        ComponentBase.__init__(self, component_name, *args, **kargs)
        self.tracewriter = tr.TraceWriter(tr.trace_fn(self.tracedir, tr.START_TRACE))
        self.tracereader = tr.TraceReader(tr.trace_fn(self.tracedir, tr.START_TRACE))

    def _get_apps_to_start(self):
        return list()

    def _get_app_options(self, app_name):
        return list()

    def _get_param_map(self, app_name):
        return {
            'ROOT': self.appdir,
        }

    def pre_start(self):
        pass

    def post_start(self):
        pass

    def configure(self):
        # First make a pass and make sure all runtime (e.g. upstart) config files are in place....
        cls = RUNNER_CLS_MAPPING[utils.fetch_run_type(self.cfg)]
        instance = cls(self.cfg, self.component_name, self.tracedir)
        tot_am = 0
        for app_info in self._get_apps_to_start():
            app_name = app_info["name"]
            app_pth = app_info.get("path", app_name)
            app_dir = app_info.get("app_dir", self.appdir)
            # Adjust the program options now that we have real locations
            program_opts = utils.param_replace_list(self._get_app_options(app_name), self._get_param_map(app_name))
            # Configure it with the given settings
            LOG.info("Configuring runner for program [%s]" % (app_name))
            cfg_am = instance.configure(app_name, (app_pth, app_dir, program_opts))
            LOG.info("Configured %s files for runner for program [%s]" % (cfg_am, app_name))
            tot_am += cfg_am
        return tot_am

    def start(self):
        # Select how we are going to start it
        cls = RUNNER_CLS_MAPPING[utils.fetch_run_type(self.cfg)]
        instance = cls(self.cfg, self.component_name, self.tracedir)
        am_started = 0
        for app_info in self._get_apps_to_start():
            app_name = app_info["name"]
            app_pth = app_info.get("path", app_name)
            app_dir = app_info.get("app_dir", self.appdir)
            # Adjust the program options now that we have real locations
            program_opts = utils.param_replace_list(self._get_app_options(app_name), self._get_param_map(app_name))
            # Start it with the given settings
            LOG.info("Starting [%s] with options [%s]" % (app_name, ", ".join(program_opts)))
            info_fn = instance.start(app_name, (app_pth, app_dir, program_opts))
            LOG.info("Started [%s] details are in [%s]" % (app_name, info_fn))
            # This trace is used to locate details about what to stop
            self.tracewriter.started_info(app_name, info_fn)
            am_started += 1
        return am_started

    def _locate_killers(self):
        start_traces = self.tracereader.apps_started()
        killer_instances = dict()
        to_kill = list()
        for (trace_fn, app_name) in start_traces:
            # Figure out which class will stop it
            killcls = None
            for (cmd, action) in tr.TraceReader(trace_fn).read():
                if cmd == settings.RUN_TYPE_TYPE and action:
                    killcls = RUNNER_CLS_MAPPING.get(action)
                    break

            # Did we find a class that can do it?
            if killcls:
                if killcls in killer_instances:
                    killer = killer_instances[killcls]
                else:
                    killer = killcls(self.cfg, self.component_name, self.tracedir)
                    killer_instances[killcls] = killer
                to_kill.append((app_name, killer))
            else:
                msg = "Could not figure out which class to use to stop (%s, %s)" % (app_name, trace_fn)
                raise excp.StopException(msg)
        return to_kill

    def stop(self):
        to_kill = self._locate_killers()
        for (app_name, killer) in to_kill:
            killer.stop(app_name)
        LOG.debug("Deleting start trace file [%s]" % (self.tracereader.filename()))
        sh.unlink(self.tracereader.filename())
        return len(to_kill)

    def status(self):
        return STATUS_UNKNOWN

    def restart(self):
        return 0


class PythonRuntime(ProgramRuntime):
    def __init__(self, component_name, *args, **kargs):
        ProgramRuntime.__init__(self, component_name, *args, **kargs)


class EmptyRuntime(ComponentBase):
    def __init__(self, component_name, *args, **kargs):
        ComponentBase.__init__(self, component_name, *args, **kargs)
        self.tracereader = tr.TraceReader(tr.trace_fn(self.tracedir, tr.IN_TRACE))

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
