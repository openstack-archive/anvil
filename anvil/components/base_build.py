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

CFG_VERSION_OVERRIDES = ['pbr_version', 'tag']


class BuildComponent(base.BasicComponent):
    pass


class PythonBuildComponent(BuildComponent):

    def __init__(self, *args, **kargs):
        super(PythonBuildComponent, self).__init__(*args, **kargs)
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
        app_dir = self.get_option('app_dir')
        pbr_version = None
        for cfg_key in CFG_VERSION_OVERRIDES:
            maybe_pbr_version = self.get_option(cfg_key)
            if maybe_pbr_version:
                pbr_version = maybe_pbr_version
                break
        egg_info = pip_helper.get_directory_details(app_dir, pbr_version=pbr_version)
        egg_info = egg_info.copy()
        egg_info['dependencies'] = pip_helper.read_requirement_files(self.requires_files)[1]
        egg_info['test_dependencies'] = pip_helper.read_requirement_files(self.test_requires_files)[1]
        return egg_info
