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
from anvil import component
from anvil import decorators
from anvil import downloader as down
from anvil import exceptions as excp
from anvil import log as logging
from anvil import patcher
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils

from anvil.components import base_packaging as bpackaging
from anvil.packaging import pip

from anvil.packaging.helpers import pip_helper

from anvil.components.configurators import base as conf

LOG = logging.getLogger(__name__)

class PkgInstallComponent(component.Component):
    def __init__(self, *args, **kargs):
        component.Component.__init__(self, *args, **kargs)
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
        pkg_list = self.get_option('packages', default_value=[])
        if not pkg_list:
            pkg_list = []
        for name, values in self.subsystems.items():
            if 'packages' in values:
                LOG.debug("Extending package list with packages for subsystem: %r", name)
                pkg_list.extend(values.get('packages'))
        return pkg_list

    def install(self):
        LOG.debug('Preparing to install packages for: %r', self.name)
        pkgs = self.packages
        if pkgs:
            pkg_names = set([p['name'] for p in pkgs])
            utils.log_iterable(pkg_names, logger=LOG,
                               header="Setting up %s distribution packages" % (len(pkg_names)))
            with utils.progress_bar('Installing', len(pkgs)) as p_bar:
                for (i, p) in enumerate(pkgs):
                    installer = bpackaging.make_packager(p, self.distro.package_manager_class,
                                              distro=self.distro)
                    installer.install(p)
                    # Mark that this happened so that we can uninstall it
                    self.tracewriter.package_installed(bpackaging.filter_package(p))
                    p_bar.update(i + 1)

    def pre_install(self):
        pkgs = self.packages
        for p in pkgs:
            installer = bpackaging.make_packager(p, self.distro.package_manager_class,
                                      distro=self.distro)
            installer.pre_install(p, self.params)

    def post_install(self):
        pkgs = self.packages
        for p in pkgs:
            installer = bpackaging.make_packager(p, self.distro.package_manager_class,
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

    def configure(self):
        return self._configure_files() + self._configure_symlinks()


class PythonInstallComponent(PkgInstallComponent):
    def __init__(self, *args, **kargs):
        PkgInstallComponent.__init__(self, *args, **kargs)
        self.requires_files = [
            sh.joinpths(self.get_option('app_dir'), 'tools', 'pip-requires'),
        ]
        if self.get_bool_option('use_tests_requires', default_value=True):
            self.requires_files.append(sh.joinpths(self.get_option('app_dir'), 'tools', 'test-requires'))

    def _get_download_config(self):
        return 'get_from'

    @property
    def python_directories(self):
        py_dirs = {}
        app_dir = self.get_option('app_dir')
        if sh.isdir(app_dir):
            py_dirs[self.name] = app_dir
        return py_dirs

    @property
    def packages(self):
        pkg_list = super(PythonInstallComponent, self).packages
        if not pkg_list:
            pkg_list = []
        pkg_list.extend(self._get_mapped_packages())
        return pkg_list

    @property
    def pips_to_packages(self):
        pip_pkg_list = self.get_option('pip_to_package', default_value=[])
        if not pip_pkg_list:
            pip_pkg_list = []
        return pip_pkg_list

    @property
    def pip_requires(self):
        all_pips = []
        for fn in self.requires_files:
            all_pips.extend(self._extract_pip_requires(fn))
        return all_pips

    def _match_pip_requires(self, pip_req):

        def pip_use(who, there_pip):
            if there_pip.key != pip_req.key:
                return False
            if not len(pip_req.specs):
                # No version/restrictions specified
                return True
            there_version = None
            if not there_pip.specs or there_pip == pip_req:
                return True
            # Different possibly incompat. versions found...
            if there_version is None:
                # Assume pip will install the correct version anyway
                if who != self.name:
                    msg = ("Component %r asked for package '%s'"
                           " and '%s' is being selected from %r instead...")
                    LOG.debug(msg, self.name, pip_req, there_pip, who)
                return True
            else:
                if who != self.name:
                    msg = ("Component %r provides package '%s'"
                           " but '%s' is being asked for by %r instead...")
                    LOG.warn(msg, who, there_pip, pip_req, self.name)
                return False

        LOG.debug("Attempting to find who satisfies pip requirement '%s'", pip_req)

        # Try to find it in anyones pip -> pkg list
        all_pip_2_pkgs = {
            self.name: self.pips_to_packages,
        }
        # Gather them all (but only if they activate before me)
        # since if they activate after, we can't depend on it
        # to satisfy our requirement...
        for (name, c) in self.instances.items():
            if c is self or not c.activated:
                continue
            if isinstance(c, (PythonInstallComponent)):
                all_pip_2_pkgs[name] = c.pips_to_packages
        for (who, pips_2_pkgs) in all_pip_2_pkgs.items():
            for pip_info in pips_2_pkgs:
                there_pip = pip.extract_requirement(pip_info)
                if not pip_use(who, there_pip):
                    continue
                LOG.debug("Matched pip->pkg '%s' from component %r", there_pip, who)
                return (dict(pip_info.get('package')), False)

        # Ok nobody had it in a pip->pkg mapping
        # but see if they had it in there pip collection
        all_pips = {
            self.name: self._base_pips(),  # Use base pips to avoid recursion...
        }
        for (name, c) in self.instances.items():
            if not c.activated or c is self:
                continue
            if isinstance(c, (PythonInstallComponent)):
                all_pips[name] = c._base_pips()  # pylint: disable=W0212
        for (who, there_pips) in all_pips.items():
            for pip_info in there_pips:
                there_pip = pip.extract_requirement(pip_info)
                if not pip_use(who, there_pip):
                    continue
                LOG.debug("Matched pip '%s' from component %r", there_pip, who)
                return (dict(pip_info), True)

        # Ok nobody had it in there pip->pkg mapping or pip mapping
        # but now lets see if we can automatically find
        # a pip->pkg mapping for them using the good ole'
        # rpm/yum database.
        installer = bpackaging.make_packager({}, self.distro.package_manager_class,
                                  distro=self.distro)

        # TODO(harlowja): make this better
        if installer and hasattr(installer, 'match_pip_2_package'):
            try:
                dist_pkg = installer.match_pip_2_package(pip_req)
                if dist_pkg:
                    pkg_info = {
                        'name': str(dist_pkg.name),
                        'version': str(dist_pkg.version),
                        '__requirement': dist_pkg,
                    }
                    LOG.debug("Auto-matched (dist) %s -> %s", pip_req, dist_pkg)
                    return (pkg_info, False)
            except excp.DependencyException as e:
                LOG.warn("Unable to automatically map pip to package: %s", e)

        # Ok still nobody has it, search pypi...
        pypi_pkg = pip_helper.find_pypi_match(pip_req)
        if pypi_pkg:
            pkg_info = {
                'name': str(pypi_pkg.key),
                '__requirement': pypi_pkg,
            }
            try:
                pkg_info['version'] = pypi_pkg.specs[0][1]
            except IndexError:
                pass
            LOG.debug("Auto-matched (pypi) %s -> %s", pip_req, pypi_pkg)
            return (pkg_info, True)

        return (None, False)

    def _get_mapped_packages(self):
        add_on_pkgs = []
        all_pips = self.pip_requires
        for details in all_pips:
            pkg_info = details['package']
            from_pip = details['from_pip']
            if from_pip or not pkg_info:
                continue
            # Keep the initial requirement
            pkg_info = dict(pkg_info)
            pkg_info['__requirement'] = details['requirement']
            add_on_pkgs.append(pkg_info)
        return add_on_pkgs

    def _get_mapped_pips(self):
        add_on_pips = []
        all_pips = self.pip_requires
        for details in all_pips:
            pkg_info = details['package']
            from_pip = details['from_pip']
            if not from_pip or not pkg_info:
                continue
            # Keep the initial requirement
            pkg_info = dict(pkg_info)
            pkg_info['__requirement'] = details['requirement']
            add_on_pips.append(pkg_info)
        return add_on_pips

    def _base_pips(self):
        pip_list = self.get_option('pips', default_value=[])
        if not pip_list:
            pip_list = []
        for (name, values) in self.subsystems.items():
            if 'pips' in values:
                LOG.debug("Extending pip list with pips for subsystem: %r" % (name))
                pip_list.extend(values.get('pips'))
        return pip_list

    @property
    def pips(self):
        pip_list = self._base_pips()
        pip_list.extend(self._get_mapped_pips())
        return pip_list

    def _install_pips(self):
        pips = self.pips
        if pips:
            pip_names = set([p['name'] for p in pips])
            utils.log_iterable(pip_names, logger=LOG,
                               header="Setting up %s python packages" % (len(pip_names)))
            with utils.progress_bar('Installing', len(pips)) as p_bar:
                for (i, p) in enumerate(pips):
                    installer = bpackaging.make_packager(p, pip.Packager,
                                              distro=self.distro)
                    installer.install(p)
                    # Note that we did it so that we can remove it...
                    self.tracewriter.pip_installed(bpackaging.filter_package(p))
                    p_bar.update(i + 1)

    def _clean_pip_requires(self):
        # Fixup these files if they exist, sometimes they have 'junk' in them
        # that anvil will install instead of pip or setup.py and we don't want
        # the setup.py file to attempt to install said dependencies since it
        # typically picks locations that either are not what we desire or if
        # said file contains editables, it may even pick external source directories
        # which is what anvil is setting up as well...
        req_fns = [f for f in self.requires_files if sh.isfile(f)]
        if req_fns:
            utils.log_iterable(req_fns, logger=LOG,
                               header="Adjusting %s pip 'requires' files" % (len(req_fns)))
            for fn in req_fns:
                old_lines = sh.load_file(fn).splitlines()
                new_lines = self._filter_pip_requires(fn, old_lines)
                contents = "# Cleaned on %s\n\n%s\n" % (utils.iso8601(), "\n".join(new_lines))
                sh.write_file_and_backup(fn, contents)
        return len(req_fns)

    def _filter_pip_requires(self, fn, lines):
        # The default does no filtering except to ensure that said lines are valid...
        return lines

    def pre_install(self):
        self._verify_pip_requires()
        PkgInstallComponent.pre_install(self)
        for p in self.pips:
            installer = bpackaging.make_packager(p, pip.Packager,
                                      distro=self.distro)
            installer.pre_install(p, self.params)

    def post_install(self):
        PkgInstallComponent.post_install(self)
        for p in self.pips:
            installer = bpackaging.make_packager(p, pip.Packager,
                                      distro=self.distro)
            installer.post_install(p, self.params)

    def _install_python_setups(self):
        py_dirs = self.python_directories
        if py_dirs:
            real_dirs = {}
            for (name, wkdir) in py_dirs.items():
                real_dirs[name] = wkdir
                if not real_dirs[name]:
                    real_dirs[name] = self.get_option('app_dir')
            utils.log_iterable(real_dirs.values(), logger=LOG,
                               header="Setting up %s python directories" % (len(real_dirs)))
            setup_cmd = self.distro.get_command('python', 'setup')
            for (name, working_dir) in real_dirs.items():
                sh.mkdirslist(working_dir, tracewriter=self.tracewriter)
                setup_fn = sh.joinpths(self.get_option('trace_dir'), "%s.python.setup" % (name))
                sh.execute(*setup_cmd, cwd=working_dir, run_as_root=True,
                           stderr_fn='%s.stderr' % (setup_fn),
                           stdout_fn='%s.stdout' % (setup_fn),
                           tracewriter=self.tracewriter)
                self.tracewriter.py_installed(name, working_dir)

    def _python_install(self):
        self._install_pips()
        self._install_python_setups()

    @decorators.memoized
    def _extract_pip_requires(self, fn):
        if not sh.isfile(fn):
            return []
        LOG.debug("Resolving dependencies from %s.", colorizer.quote(fn))
        pips_needed = pip_helper.parse_requirements(sh.load_file(fn))
        matchings = []
        for req in pips_needed:
            (pkg_info, from_pip) = self._match_pip_requires(req)
            matchings.append({
                'requirement': req,
                'package': pkg_info,
                'from_pip': from_pip,
                'needed_by': fn,
            })
        return matchings

    def _verify_pip_requires(self):
        all_pips = self.pip_requires
        for details in all_pips:
            req = details['requirement']
            needed_by = details['needed_by']
            pkg_info = details['package']
            if not pkg_info:
                raise excp.DependencyException(("Pip dependency '%s' needed by '%s' is not translatable to a listed"
                                                " (from this or previously activated components) pip package"
                                                ' or a pip->package mapping!') % (req, needed_by))

    def install(self):
        PkgInstallComponent.install(self)
        self._python_install()

    def configure(self):
        configured_am = PkgInstallComponent.configure(self)
        configured_am += self._clean_pip_requires()
        return configured_am
