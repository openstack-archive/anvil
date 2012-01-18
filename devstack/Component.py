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

#TODO fix these
from Util import (component_pths,
                  get_pkg_list,
                  get_pip_list,
                  param_replace,
                  STACK_CONFIG_DIR)
from Shell import (execute, mkdirslist, write_file,
                    load_file, joinpths, touch_file,
                    unlink, deldir)
from Trace import (TraceWriter, TraceReader,
                    touch_trace, parse_fn,
                    IN_TRACE, PY_TRACE, START_TRACE)
from runners import Foreground, Screen
from runners.Foreground import (ForegroundRunner)
from runners.Screen import ScreenRunner
from Exceptions import (StopException, StartException, InstallException)

import Downloader
import Logger
import Pip
import Runner

LOG = Logger.getLogger("install.component")
PY_INSTALL = ['python', 'setup.py', 'develop']
PY_UNINSTALL = ['python', 'setup.py', 'develop', '--uninstall']


class ComponentBase():
    def __init__(self, component_name, *args, **kargs):
        self.cfg = kargs.get("cfg")
        self.packager = kargs.get("pkg")
        self.distro = kargs.get("distro")
        self.root = kargs.get("root")
        self.othercomponents = set(kargs.get("components", []))
        pths = component_pths(self.root, component_name)
        self.componentroot = pths.get('root_dir')
        self.tracedir = pths.get("trace_dir")
        self.appdir = pths.get("app_dir")
        self.cfgdir = pths.get('config_dir')
        self.component_name = component_name

#
#the following are just interfaces...
#


class InstallComponent():
    def download(self):
        raise NotImplementedError()

    def configure(self):
        raise NotImplementedError()

    def install(self):
        raise NotImplementedError()


class UninstallComponent():
    def unconfigure(self):
        raise NotImplementedError()

    def uninstall(self):
        raise NotImplementedError()


class RuntimeComponent():
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
        self.tracewriter = TraceWriter(self.tracedir, IN_TRACE)

    def _get_download_location(self):
        raise NotImplementedError()

    def download(self):
        #find out where to get it
        (uri, branch) = self._get_download_location()
        if(uri):
            #now get it
            dirsmade = Downloader.download(self.appdir, uri, branch)
            #this trace isn't used yet but could be
            self.tracewriter.downloaded(self.appdir, uri)
            #this trace is used to remove the dirs created
            self.tracewriter.dir_made(*dirsmade)
        return self.tracedir

    def _get_param_map(self, fn=None):
        return None

    def _do_pkg_install(self):
        pkgs = get_pkg_list(self.distro, self.component_name)
        if(len(pkgs)):
            pkgnames = sorted(pkgs.keys())
            LOG.debug("Installing packages %s" % (", ".join(pkgnames)))
            mp = self._get_param_map()
            #run pre, install, then post
            self.packager.pre_install(pkgs, mp)
            self.packager.install_batch(pkgs)
            self.packager.post_install(pkgs, mp)
            #add trace used to remove the pkgs
            for name in pkgnames:
                self.tracewriter.package_install(name, pkgs.get(name))

    def install(self):
        self._do_pkg_install()
        return self.tracedir

    def _get_config_files(self):
        return list()

    def _config_adjust(fn, contents):
        return contents

    def configure(self):
        dirsmade = mkdirslist(self.cfgdir)
        self.tracewriter.dir_made(*dirsmade)
        configs = self._get_config_files()
        if(configs and len(configs)):
            for fn in configs:
                parameters = self._get_param_map(fn)
                sourcefn = joinpths(STACK_CONFIG_DIR, self.component_name, fn)
                tgtfn = joinpths(self.cfgdir, fn)
                LOG.info("Configuring template file %s" % (sourcefn))
                contents = load_file(sourcefn)
                LOG.info("Replacing parameters in file %s" % (sourcefn))
                LOG.debug("Replacements = %s" % (parameters))
                contents = param_replace(contents, parameters)
                LOG.debug("Applying side-effects of param replacement for template %s" % (sourcefn))
                contents = self._config_adjust(contents, fn)
                LOG.info("Writing configuration file %s" % (tgtfn))
                write_file(tgtfn, contents)
                #this trace is used to remove the files configured
                self.tracewriter.cfg_write(tgtfn)
        return self.tracedir


class PythonInstallComponent(PkgInstallComponent):
    def __init__(self, component_name, *args, **kargs):
        PkgInstallComponent.__init__(self, component_name, *args, **kargs)

    def _python_install(self):
        pips = get_pip_list(self.distro, self.component_name)
        #install any need pip items
        if(len(pips)):
            Pip.install(pips)
            for name in pips.keys():
                self.tracewriter.pip_install(name, pips.get(name))
        #do the actual python install
        dirsmade = mkdirslist(self.tracedir)
        self.tracewriter.dir_made(*dirsmade)
        recordwhere = touch_trace(self.tracedir, PY_TRACE)
        self.tracewriter.py_install(recordwhere)
        (sysout, stderr) = execute(*PY_INSTALL, cwd=self.appdir, run_as_root=True)
        write_file(recordwhere, sysout)

    # Overridden
    def install(self):
        self._do_pkg_install()
        self._python_install()
        return self.tracedir


class PkgUninstallComponent(ComponentBase, UninstallComponent):
    def __init__(self, component_name, *args, **kargs):
        ComponentBase.__init__(self, component_name, *args, **kargs)
        self.tracereader = TraceReader(self.tracedir, IN_TRACE)

    def unconfigure(self):
        self._unconfigure_files()

    def _unconfigure_files(self):
        cfgfiles = self.tracereader.files_configured()
        if(len(cfgfiles)):
            LOG.info("Removing %s configuration files" % (len(cfgfiles)))
            for fn in cfgfiles:
                if(len(fn)):
                    unlink(fn)
                    LOG.info("Removed %s" % (fn))

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
                    unlink(fn)
                    LOG.info("Removed %s" % (fn))

    def _uninstall_dirs(self):
        dirsmade = self.tracereader.dirs_made()
        if(len(dirsmade)):
            LOG.info("Removing %s created directories" % (len(dirsmade)))
            for dirname in dirsmade:
                deldir(dirname)
                LOG.info("Removed %s" % (dirname))


class PythonUninstallComponent(PkgUninstallComponent):
    def __init__(self, component_name, *args, **kargs):
        PkgUninstallComponent.__init__(self, component_name, *args, **kargs)

    def uninstall(self):
        self._uninstall_pkgs()
        self._uninstall_touched_files()
        self._uninstall_python()
        self._uninstall_dirs()

    def _uninstall_python(self):
        pylisting = self.tracereader.py_listing()
        if(pylisting and len(pylisting)):
            execute(*PY_UNINSTALL, cwd=self.appdir, run_as_root=True)


class ProgramRuntime(ComponentBase, RuntimeComponent):
    #this here determines how we start and stop and
    #what classes handle different running/stopping types
    STARTER_CLS_MAPPING = {
        Foreground.RUN_TYPE: ForegroundRunner,
        Screen.RUN_TYPE: ScreenRunner,
    }
    STOPPER_CLS_MAPPING = {
        Foreground.RUN_TYPE: ForegroundRunner,
        Screen.RUN_TYPE: ScreenRunner,
    }

    def __init__(self, component_name, *args, **kargs):
        ComponentBase.__init__(self, component_name, *args, **kargs)
        self.run_type = kargs.get("run_type", Foreground.RUN_TYPE)
        self.tracereader = TraceReader(self.tracedir, IN_TRACE)
        self.tracewriter = TraceWriter(self.tracedir, START_TRACE)
        self.starttracereader = TraceReader(self.tracedir, START_TRACE)
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
        raise NotImplementedError()

    def _get_app_options(self, app):
        return None

    def _get_param_map(self, app=None):
        return {
            'ROOT': self.appdir,
        }

    def start(self):
        #ensure it was installed
        if(not self._was_installed()):
            msg = "Can not start %s since it was not installed" % (self.component_name)
            raise StartException(msg)
        #select how we are going to start it
        startercls = self._getstartercls(self.run_type)
        starter = startercls()
        #start all apps
        #this fns list will have info about what was started
        fns = list()
        apps = self._get_apps_to_start()
        for app in apps:
            #adjust the program options now that we have real locations
            params = self._get_param_map(app)
            program_opts = self._get_app_options(app)
            if(params and program_opts):
                adjusted_opts = list()
                for opt in program_opts:
                    adjusted_opts.append(param_replace(opt, params))
                program_opts = adjusted_opts
            LOG.info("Starting %s with options [%s]" % (app, ", ".join(program_opts)))
            #start it with the given settings
            fn = starter.start(app, app, *program_opts, app_dir=self.appdir, trace_dir=self.tracedir)
            if(fn and len(fn)):
                fns.append(fn)
                LOG.info("Started %s, details are in %s" % (app, fn))
                #this trace is used to locate details about what to stop
                self.tracewriter.started_info(app, fn)
            else:
                LOG.info("Started %s" % (app))
        return fns

    def stop(self):
        #ensure it was installed
        if(not self._was_installed()):
            msg = "Can not stop %s since it was not installed" % (self.component_name)
            raise StopException(msg)
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
            contents = parse_fn(fn)
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
            unlink(fn)


class PythonRuntime(ProgramRuntime):
    def __init__(self, component_name, *args, **kargs):
        ProgramRuntime.__init__(self, component_name, *args, **kargs)

    def _was_installed(self):
        parent_result = ProgramRuntime._was_installed(self)
        if(not parent_result):
            return False
        python_installed = self.tracereader.py_listing()
        if(len(python_installed) == 0):
            return False
        else:
            return True
