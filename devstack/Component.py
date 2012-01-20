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

import os
import os.path

import Downloader
import Exceptions
import Logger
import Pip
import Runner
import runners.Foreground
import runners.Screen
import Shell
import Trace
import Util


LOG = Logger.getLogger("install.component")
PY_INSTALL = ['python', 'setup.py', 'develop']
PY_UNINSTALL = ['python', 'setup.py', 'develop', '--uninstall']


class ComponentBase():
    def __init__(self, component_name, **kargs):
        self.cfg = kargs.get("cfg")
        self.packager = kargs.get("pkg")
        self.distro = kargs.get("distro")
        self.root = kargs.get("root")
        self.all_components = set(kargs.get("components", []))
        (self.componentroot, self.tracedir,
            self.appdir, self.cfgdir) = Util.component_paths(self.root, component_name)
        self.component_name = component_name
        self.component_info = kargs.get('component_info')

#
#the following are just interfaces...
#


class InstallComponent():
    def __init__(self):
        pass

    def download(self):
        raise NotImplementedError()

    def configure(self):
        raise NotImplementedError()

    def pre_install(self):
        raise NotImplementedError()

    def install(self):
        raise NotImplementedError()

    def post_install(self):
        raise NotImplementedError()


class UninstallComponent():
    def __init__(self):
        pass

    def unconfigure(self):
        raise NotImplementedError()

    def uninstall(self):
        raise NotImplementedError()


class RuntimeComponent():
    def __init__(self):
        pass

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def status(self):
        raise NotImplementedError()

    def restart(self):
        raise NotImplementedError()


# useful impls


class PkgInstallComponent(ComponentBase, InstallComponent):
    def __init__(self, component_name, *args, **kargs):
        ComponentBase.__init__(self, component_name, *args, **kargs)
        InstallComponent.__init__(self)
        self.tracewriter = Trace.TraceWriter(self.tracedir, Trace.IN_TRACE)

    def _get_download_locations(self):
        return list()

    def download(self):
        locations = self._get_download_locations()
        base_dir = self.appdir
        am_downloaded = 0
        for location_info in locations:
            uri = location_info.get("uri")
            if(not uri):
                continue
            branch = location_info.get("branch")
            subdir = location_info.get("subdir")
            target_loc = None
            if(subdir and len(subdir)):
                target_loc = Shell.joinpths(base_dir, subdir)
            else:
                target_loc = base_dir
            dirsmade = Downloader.download(target_loc, uri, branch)
            self.tracewriter.downloaded(target_loc, uri)
            self.tracewriter.dir_made(*dirsmade)
            am_downloaded += 1
        return am_downloaded

    def _get_param_map(self, config_fn):
        return None

    def install(self):
        pkgs = Util.get_pkg_list(self.distro, self.component_name)
        if(len(pkgs)):
            pkgnames = sorted(pkgs.keys())
            LOG.info("Installing packages %s" % (", ".join(pkgnames)))
            self.packager.install_batch(pkgs)
            #add trace used to remove the pkgs
            for name in pkgnames:
                self.tracewriter.package_install(name, pkgs.get(name))
        return self.tracedir

    def pre_install(self):
        pkgs = Util.get_pkg_list(self.distro, self.component_name)
        if(len(pkgs)):
            mp = self._get_param_map(None)
            self.packager.pre_install(pkgs, mp)
        return self.tracedir

    def post_install(self):
        pkgs = Util.get_pkg_list(self.distro, self.component_name)
        if(len(pkgs)):
            mp = self._get_param_map(None)
            self.packager.post_install(pkgs, mp)
        return self.tracedir

    def _get_config_files(self):
        return list()

    def _config_adjust(self, contents, config_fn):
        return contents

    def _get_target_config_name(self, name):
        return Shell.joinpths(self.cfgdir, name)

    def _get_source_config_name(self, name):
        return Shell.joinpths(Util.STACK_CONFIG_DIR, self.component_name, name)

    def configure(self):
        dirsmade = Shell.mkdirslist(self.cfgdir)
        self.tracewriter.dir_made(*dirsmade)
        configs = self._get_config_files()
        am = len(configs)
        for fn in configs:
            #get the params and where it should come from and where it should go
            parameters = self._get_param_map(fn)
            sourcefn = self._get_source_config_name(fn)
            tgtfn = self._get_target_config_name(fn)
            #ensure directory is there (if not created previously)
            dirsmade = Shell.mkdirslist(os.path.dirname(tgtfn))
            self.tracewriter.dir_made(*dirsmade)
            #now configure it
            LOG.info("Configuring template file %s" % (sourcefn))
            contents = Shell.load_file(sourcefn)
            LOG.info("Replacing parameters in file %s" % (sourcefn))
            LOG.debug("Replacements = %s" % (parameters))
            contents = Util.param_replace(contents, parameters)
            LOG.debug("Applying side-effects of param replacement for template %s" % (sourcefn))
            contents = self._config_adjust(contents, fn)
            LOG.info("Writing configuration file %s" % (tgtfn))
            #this trace is used to remove the files configured
            Shell.write_file(tgtfn, contents)
            self.tracewriter.cfg_write(tgtfn)
        return am


class PythonInstallComponent(PkgInstallComponent):
    def __init__(self, component_name, *args, **kargs):
        PkgInstallComponent.__init__(self, component_name, *args, **kargs)

    def _get_python_directories(self):
        py_dirs = list()
        py_dirs.append({
                'name': self.component_name,
                'work_dir': self.appdir,
        })
        return py_dirs

    def _install_pips(self):
        pips = Util.get_pip_list(self.distro, self.component_name)
        #install any need pip items
        if(len(pips)):
            LOG.info("Setting up %s pips" % (len(pips)))
            Pip.install(pips)
            for name in pips.keys():
                self.tracewriter.pip_install(name, pips.get(name))

    def _format_stderr_out(self, stderr, stdout):
        if(stdout == None):
            stdout = ''
        if(stderr == None):
            stderr = ''
        combined_output = "===STDOUT===" + os.linesep
        combined_output += stdout + os.linesep
        combined_output += "===STDERR===" + os.linesep
        combined_output += stderr + os.linesep
        return combined_output

    def _format_trace_name(self, name):
        return "%s-%s" % (Trace.PY_TRACE, name)

    def _install_python_setups(self):
        pydirs = self._get_python_directories()
        if(len(pydirs)):
            LOG.info("Setting up %s python directories" % (len(pydirs)))
            dirsmade = Shell.mkdirslist(self.tracedir)
            self.tracewriter.dir_made(*dirsmade)
            for pydir_info in pydirs:
                name = pydir_info.get("name")
                working_dir = pydir_info.get('work_dir', self.appdir)
                record_fn = Trace.touch_trace(self.tracedir, self._format_trace_name(name))
                self.tracewriter.file_touched(record_fn)
                (stdout, stderr) = Shell.execute(*PY_INSTALL, cwd=working_dir, run_as_root=True)
                Shell.write_file(record_fn, self._format_stderr_out(stderr, stdout))
                self.tracewriter.py_install(name, record_fn, working_dir)

    def _python_install(self):
        self._install_pips()
        self._install_python_setups()

    def install(self):
        parent_result = PkgInstallComponent.install(self)
        self._python_install()
        return parent_result


class PkgUninstallComponent(ComponentBase, UninstallComponent):
    def __init__(self, component_name, *args, **kargs):
        ComponentBase.__init__(self, component_name, *args, **kargs)
        UninstallComponent.__init__(self)
        self.tracereader = Trace.TraceReader(self.tracedir, Trace.IN_TRACE)

    def unconfigure(self):
        self._unconfigure_files()

    def _unconfigure_files(self):
        cfgfiles = self.tracereader.files_configured()
        if(len(cfgfiles)):
            LOG.info("Removing %s configuration files" % (len(cfgfiles)))
            for fn in cfgfiles:
                if(len(fn)):
                    Shell.unlink(fn)

    def uninstall(self):
        self._uninstall_pkgs()
        self._uninstall_touched_files()
        self._uninstall_dirs()

    def _uninstall_pkgs(self):
        pkgsfull = self.tracereader.packages_installed()
        if(len(pkgsfull)):
            LOG.info("Potentially removing %s packages" % (len(pkgsfull)))
            self.packager.remove_batch(pkgsfull)

    def _uninstall_touched_files(self):
        filestouched = self.tracereader.files_touched()
        if(len(filestouched)):
            LOG.info("Removing %s touched files" % (len(filestouched)))
            for fn in filestouched:
                if(len(fn)):
                    Shell.unlink(fn)

    def _uninstall_dirs(self):
        dirsmade = self.tracereader.dirs_made()
        if(len(dirsmade)):
            LOG.info("Removing %s created directories" % (len(dirsmade)))
            for dirname in dirsmade:
                Shell.deldir(dirname)


class PythonUninstallComponent(PkgUninstallComponent):
    def __init__(self, component_name, *args, **kargs):
        PkgUninstallComponent.__init__(self, component_name, *args, **kargs)

    def uninstall(self):
        self._uninstall_pkgs()
        self._uninstall_pips()
        self._uninstall_touched_files()
        self._uninstall_python()
        self._uninstall_dirs()

    def _uninstall_pips(self):
        pips = self.tracereader.pips_installed()
        if(pips and len(pips)):
            LOG.info("Uninstalling %s pips" % (len(pips)))
            Pip.uninstall(pips)

    def _uninstall_python(self):
        pylisting = self.tracereader.py_listing()
        if(pylisting and len(pylisting)):
            LOG.info("Uninstalling %s python setups" % (len(pylisting)))
            for entry in pylisting:
                where = entry.get('where')
                Shell.execute(*PY_UNINSTALL, cwd=where, run_as_root=True)


class ProgramRuntime(ComponentBase, RuntimeComponent):
    #this here determines how we start and stop and
    #what classes handle different running/stopping types
    STARTER_CLS_MAPPING = {
        runners.Foreground.RUN_TYPE: runners.Foreground.ForegroundRunner,
        runners.Screen.RUN_TYPE: runners.Screen.ScreenRunner,
    }
    STOPPER_CLS_MAPPING = {
        runners.Foreground.RUN_TYPE: runners.Foreground.ForegroundRunner,
        runners.Screen.RUN_TYPE: runners.Screen.ScreenRunner,
    }

    def __init__(self, component_name, *args, **kargs):
        ComponentBase.__init__(self, component_name, *args, **kargs)
        RuntimeComponent.__init__(self)
        self.run_type = kargs.get("run_type", runners.Foreground.RUN_TYPE)
        self.tracereader = Trace.TraceReader(self.tracedir, Trace.IN_TRACE)
        self.tracewriter = Trace.TraceWriter(self.tracedir, Trace.START_TRACE)
        self.starttracereader = Trace.TraceReader(self.tracedir, Trace.START_TRACE)
        self.check_installed_pkgs = kargs.get("check_installed_pkgs", True)

    def _getstartercls(self, start_mode):
        if(start_mode not in ProgramRuntime.STARTER_CLS_MAPPING):
            raise NotImplementedError("Can not yet start %s mode" % (start_mode))
        return ProgramRuntime.STARTER_CLS_MAPPING.get(start_mode)

    def _getstoppercls(self, stop_mode):
        if(stop_mode not in ProgramRuntime.STOPPER_CLS_MAPPING):
            raise NotImplementedError("Can not yet stop %s mode" % (stop_mode))
        return ProgramRuntime.STOPPER_CLS_MAPPING.get(stop_mode)

    def _was_installed(self):
        if(not self.check_installed_pkgs):
            return True
        if(len(self.tracereader.packages_installed())):
            return True
        return False

    def _get_apps_to_start(self):
        return list()

    def _get_app_options(self, app_name):
        return list()

    def _get_param_map(self, app_name):
        return {
            'ROOT': self.appdir,
        }

    def start(self):
        #ensure it was installed
        if(not self._was_installed()):
            msg = "Can not start %s since it was not installed" % (self.component_name)
            raise Exceptions.StartException(msg)
        #select how we are going to start it
        startercls = self._getstartercls(self.run_type)
        starter = startercls()
        #start all apps
        #this fns list will have info about what was started
        fns = list()
        apps = self._get_apps_to_start()
        for app_info in apps:
            #extract needed keys
            app_name = app_info.get("name")
            app_pth = app_info.get("path", app_name)
            app_dir = app_info.get("app_dir", self.appdir)
            #adjust the program options now that we have real locations
            params = self._get_param_map(app_name)
            program_opts = self._get_app_options(app_name)
            if(params and program_opts):
                adjusted_opts = list()
                for opt in program_opts:
                    adjusted_opts.append(Util.param_replace(opt, params))
                program_opts = adjusted_opts
            LOG.info("Starting [%s] with options [%s]" % (app_name, ", ".join(program_opts)))
            #start it with the given settings
            fn = starter.start(app_name, app_pth, *program_opts, app_dir=app_dir, \
                               trace_dir=self.tracedir)
            if(fn):
                fns.append(fn)
                LOG.info("Started %s, details are in %s" % (app_name, fn))
                #this trace is used to locate details about what to stop
                self.tracewriter.started_info(app_name, fn)
            else:
                LOG.info("Started %s" % (app_name))
        return fns

    def stop(self):
        #ensure it was installed
        if(not self._was_installed()):
            msg = "Can not stop %s since it was not installed" % (self.component_name)
            raise Exceptions.StopException(msg)
        #we can only stop what has a started trace
        start_traces = self.starttracereader.apps_started()
        killedam = 0
        for mp in start_traces:
            #extract the apps name and where its trace is
            fn = mp.get('trace_fn')
            name = mp.get('name')
            #missing some key info, skip it
            if(fn == None or name == None):
                continue
            #figure out which class will stop it
            contents = Trace.parse_fn(fn)
            killcls = None
            for (cmd, action) in contents:
                if(cmd == Runner.RUN_TYPE):
                    killcls = self._getstoppercls(action)
                    break
            #did we find a class that can do it?
            if(killcls):
                #we can try to stop it
                LOG.info("Stopping %s" % (name))
                #create an instance of the killer class and attempt to stop
                killer = killcls()
                killer.stop(name, trace_dir=self.tracedir)
                killedam += 1
        #if we got rid of them all get rid of the trace
        if(killedam == len(start_traces)):
            fn = self.starttracereader.trace_fn
            LOG.info("Deleting trace file %s" % (fn))
            Shell.unlink(fn)
        return killedam

    def status(self):
        return None

    def restart(self):
        return 0


class PythonRuntime(ProgramRuntime):
    def __init__(self, component_name, *args, **kargs):
        ProgramRuntime.__init__(self, component_name, *args, **kargs)

    def status(self):
        return None

    def restart(self):
        return 0

    def _was_installed(self):
        parent_result = ProgramRuntime._was_installed(self)
        if(not parent_result):
            return False
        python_installed = self.tracereader.py_listing()
        if(len(python_installed) == 0):
            return False
        else:
            return True


class NullRuntime(ComponentBase, RuntimeComponent):
    def __init__(self, component_name, *args, **kargs):
        ComponentBase.__init__(self, component_name, *args, **kargs)
        RuntimeComponent.__init__(self)

    def start(self):
        return 0

    def stop(self):
        return 0

    def status(self):
        return None

    def restart(self):
        return 0
