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

from anvil import colorizer
from anvil import component
from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils

from anvil.components import base_packaging as bpackaging
from anvil.packaging import pip

LOG = logging.getLogger(__name__)

class PkgUninstallComponent(component.Component):
    def __init__(self, *args, **kargs):
        component.Component.__init__(self, *args, **kargs)
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

    def uninstall(self):
        self._uninstall_pkgs()
        self._uninstall_files()

    def post_uninstall(self):
        self._uninstall_dirs()

    def pre_uninstall(self):
        pass

    def _uninstall_pkgs(self):
        pkgs = self.tracereader.packages_installed()
        if pkgs:
            pkg_names = set([p['name'] for p in pkgs])
            utils.log_iterable(pkg_names, logger=LOG,
                               header="Potentially removing %s distribution packages" % (len(pkg_names)))
            which_removed = []
            with utils.progress_bar('Uninstalling', len(pkgs), reverse=True) as p_bar:
                for (i, p) in enumerate(pkgs):
                    uninstaller = bpackaging.make_packager(p, self.distro.package_manager_class,
                                                distro=self.distro,
                                                remove_default=self.purge_packages)
                    if uninstaller.remove(p):
                        which_removed.append(p['name'])
                    p_bar.update(i + 1)
            utils.log_iterable(which_removed, logger=LOG,
                               header="Actually removed %s distribution packages" % (len(which_removed)))

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


class PythonUninstallComponent(PkgUninstallComponent):

    def uninstall(self):
        self._uninstall_python()
        self._uninstall_pips()
        PkgUninstallComponent.uninstall(self)

    def _uninstall_pips(self):
        pips = self.tracereader.pips_installed()
        if pips:
            pip_names = set([p['name'] for p in pips])
            utils.log_iterable(pip_names, logger=LOG,
                               header="Potentially removing %s python packages" % (len(pip_names)))
            which_removed = []
            with utils.progress_bar('Uninstalling', len(pips), reverse=True) as p_bar:
                for (i, p) in enumerate(pips):
                    try:
                        uninstaller = bpackaging.make_packager(p, pip.Packager,
                                                    distro=self.distro,
                                                    remove_default=self.purge_packages)
                        if uninstaller.remove(p):
                            which_removed.append(p['name'])
                    except excp.ProcessExecutionError as e:
                        # NOTE(harlowja): pip seems to die if a pkg isn't there even in quiet mode
                        combined = (str(e.stderr) + str(e.stdout))
                        if not re.search(r"not\s+installed", combined, re.I):
                            raise
                    p_bar.update(i + 1)
            utils.log_iterable(which_removed, logger=LOG,
                               header="Actually removed %s python packages" % (len(which_removed)))

    def _uninstall_python(self):
        py_listing = self.tracereader.py_listing()
        if py_listing:
            py_listing_dirs = set()
            for (_name, where) in py_listing:
                py_listing_dirs.add(where)
            utils.log_iterable(py_listing_dirs, logger=LOG,
                               header="Uninstalling %s python setups" % (len(py_listing_dirs)))
            unsetup_cmd = self.distro.get_command('python', 'unsetup')
            for where in py_listing_dirs:
                if sh.isdir(where):
                    sh.execute(*unsetup_cmd, cwd=where, run_as_root=True)
                else:
                    LOG.warn("No python directory found at %s - skipping", colorizer.quote(where, quote_color='red'))
