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

import copy

from anvil import colorizer
from anvil import component as comp
from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import trace as tr
from anvil import type_utils as tu
from anvil import utils

from anvil.packaging.helpers import changelog
from anvil.packaging.helpers import yum_helper

LOG = logging.getLogger(__name__)


class DependencyPackager(comp.Component):
    def __init__(self, *args, **kargs):
        comp.Component.__init__(self, *args, **kargs)
        trace_fn = tr.trace_filename(self.get_option('trace_dir'), 'created')
        self.tracewriter = tr.TraceWriter(trace_fn, break_if_there=False)
        self.package_dir = sh.joinpths(self.get_option('component_dir'), 'package')
        self.match_installed = tu.make_bool(kargs.get('match_installed'))
        self._build_paths = None
        self._details = None

    @property
    def build_paths(self):
        if self._build_paths is None:
            bpaths = {}
            for name in ['sources', 'specs', 'srpms', 'rpms', 'build']:
                final_path = sh.joinpths(self.package_dir, name.upper())
                bpaths[name] = final_path
                if sh.isdir(final_path):
                    sh.deldir(final_path, True)
                self.tracewriter.dirs_made(*sh.mkdirslist(final_path))
            self._build_paths = bpaths
        return dict(self._build_paths)

    def _requirements(self):
        return {
            'install': self._install_requirements(),
            'build': self._build_requirements(),
        }

    def _match_version_installed(self, yum_pkg):
        if not self.match_installed:
            return yum_pkg
        installed_pkg = yum_helper.get_installed(yum_pkg['name'])
        if not installed_pkg:
            return yum_pkg
        pkg_new = copy.deepcopy(yum_pkg)
        pkg_new['version'] = installed_pkg.printVer()
        return pkg_new

    @property
    def details(self):
        if self._details is not None:
            return self._details
        self._details = {
            'name': self.name,
            'version': 0,
            'release': self.get_int_option('release', default_value=1),
            'packager': "%s <%s@%s>" % (sh.getuser(), sh.getuser(), sh.hostname()),
            'changelog': '',
            'license': 'Apache License, Version 2.0',
            'automatic_dependencies': True,
            'vendor': None,
            'url': '',
            'description': '',
            'summary': 'Package build of %s on %s' % (self.name, utils.iso8601()),
        }
        return self._details

    def _build_details(self):
        return {
            'arch': 'noarch',
        }

    def _gather_files(self):
        source_fn = self._make_source_archive()
        sources = []
        if source_fn:
            sources.append(source_fn)
        return {
            'sources': sources,
            'files': [],
            'directories': [],
            'docs': [],
        }

    def _defines(self):
        define_what = []
        define_what.append("_topdir %s" % (self.package_dir))
        return define_what

    def _undefines(self):
        undefine_what = []
        return undefine_what

    def _make_source_archive(self):
        return None

    def _make_fn(self, ext):
        your_fn = "%s-%s-%s.%s" % (self.details['name'], 
                                   self.details['version'],
                                   self.details['release'], ext)
        return your_fn

    def _obsoletes(self):
        return []

    def _conflicts(self):
        return []

    def _create_package(self):
        files = self._gather_files()
        params = {
            'files': files,
            'requires': self._requirements(),
            'obsoletes': self._obsoletes(),
            'conflicts': self._conflicts(),
            'defines': self._defines(),
            'undefines': self._undefines(),
            'build': self._build_details(),
            'who': sh.getuser(),
            'date': utils.iso8601(),
            'details': self.details,
        }
        (_fn, content) = utils.load_template('packaging', 'spec.tmpl')
        spec_base = self._make_fn("spec")
        spec_fn = sh.joinpths(self.build_paths['specs'], spec_base)
        LOG.debug("Creating spec file %s with params:", spec_fn)
        files['sources'].append("%s.tar.gz" % (spec_base))
        utils.log_object(params, logger=LOG, level=logging.DEBUG)
        sh.write_file(spec_fn, utils.expand_template(content, params))
        tar_it(sh.joinpths(self.build_paths['sources'], "%s.tar.gz" % (spec_base)),
               spec_base, wkdir=self.build_paths['specs'])

    def _build_requirements(self):
        return []

    def _install_requirements(self):
        i_sibling = self.siblings.get('install')
        if not i_sibling:
            return []
        requirements = []
        for p in i_sibling.packages:
            p = self._match_version_installed(p)
            if 'version' in p:
                requirements.append("%s = %s" % (p['name'], p['version']))
            else:
                requirements.append("%s" % (p['name']))
        return requirements

    def package(self):
        self._create_package()
        return self.package_dir 


class PythonPackager(DependencyPackager):
    def __init__(self, *args, **kargs):
        DependencyPackager.__init__(self, *args, **kargs)
        self._extended_details = None
        self._setup_fn = sh.joinpths(self.get_option('app_dir'), 'setup.py')
        
    def _build_requirements(self):
        return [
            'python',
            'python-devel',
            'gcc', # Often used for building c python modules, should not be harmful...
            'python-setuptools',
        ]

    def _build_changelog(self):
        try:
            ch = changelog.RpmChangeLog(self.get_option('app_dir'))
            return ch.format_log()
        except (excp.AnvilException, IOError):
            return ''

    def _undefines(self):
        undefine_what = DependencyPackager._undefines(self)
        if self.get_bool_option('ignore-missing'):
            undefine_what.append('__check_files')
        return undefine_what

    def _gather_files(self):
        files = DependencyPackager._gather_files(self)
        files['directories'].append("%{python_sitelib}/" + (self.details['name']))
        files['files'].append("%{python_sitelib}/" + (self.details['name']))
        files['files'].append("%{python_sitelib}/" + "%s-*.egg-info/" % (self.details['name']))
        files['files'].append("%{_bindir}/")
        return files

    def _build_details(self):
        # See: http://www.rpm.org/max-rpm/s1-rpm-inside-macros.html
        b_dets = DependencyPackager._build_details(self)
        b_dets['setup'] = '-q -n %{name}-%{version}'
        b_dets['action'] = '%{__python} setup.py build'
        b_dets['install_how'] = '%{__python} setup.py install --prefix=%{_prefix} --root=%{buildroot}'
        return b_dets

    def verify(self):
        if not sh.isfile(self._setup_fn):
            raise excp.PackageException(("Can not package %s since python"
                                         " setup file at %s is missing") % (self.name, self._setup_fn))

    def _make_source_archive(self):
        with utils.tempdir() as td:
            arch_base_name = "%s-%s" % (self.details['name'], self.details['version'])
            sh.copytree(self.get_option('app_dir'), sh.joinpths(td, arch_base_name))
            arch_tmp_fn = sh.joinpths(td, "%s.tar.gz" % (arch_base_name))
            tar_it(arch_tmp_fn, arch_base_name, td)
            sh.move(arch_tmp_fn, self.build_paths['sources'])
        return "%s.tar.gz" % (arch_base_name)

    def _description(self):
        describe_cmd = ['python', self._setup_fn, '--description']
        (stdout, _stderr) = sh.execute(*describe_cmd, run_as_root=True, cwd=self.get_option('app_dir'))
        stdout = stdout.strip()
        if stdout:
            # RPM apparently rejects descriptions with blank lines (even between content)
            descr_lines = []
            for line in stdout.splitlines():
                sline = line.strip()
                if not sline:
                    continue
                else:
                    descr_lines.append(line)
            return descr_lines
        return []

    @property
    def details(self):
        base = super(PythonPackager, self).details
        if self._extended_details is None:
            ext_dets = {
                'automatic_dependencies': False,
            }
            setup_cmd = ['python', self._setup_fn]
            replacements = {
                'version': '--version',
                'license': '--license',
                'name': '--name',
                'vendor': '--author',
                'url': '--url',
            }
            for (key, opt) in replacements.items():
                cmd = setup_cmd + [opt]
                (stdout, _stderr) = sh.execute(*cmd, run_as_root=True, cwd=self.get_option('app_dir'))
                stdout = stdout.strip()
                if stdout:
                    ext_dets[key] = stdout
            description = self._description()
            if description:
                ext_dets['description'] = "\n".join(description)
                ext_dets['summary'] = utils.truncate_text("\n".join(description[0:1]), 50)
            ext_dets['changelog'] = self._build_changelog()
            self._extended_details = ext_dets
        extended_dets = dict(base)
        extended_dets.update(self._extended_details)
        return extended_dets

    def package(self):
        i_sibling = self.siblings.get('install')
        pips = []
        if i_sibling:
            pips.extend(i_sibling.pips)
        if pips:
            for pip_info in pips:
                LOG.warn("Unable to package pip %s dependency in an rpm.", colorizer.quote(pip_info['name']))
        return DependencyPackager.package(self)


def tar_it(to_where, what, wkdir):
    tar_cmd = ['tar', '-cvzf', to_where, what]
    return sh.execute(*tar_cmd, cwd=wkdir)
