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

import json

from anvil import exceptions as excp
from anvil import shell as sh

# Common trace actions
AP_STARTED = "AP_STARTED"
CFG_WRITING_FILE = "CFG_WRITING_FILE"
DIR_MADE = "DIR_MADE"
DOWNLOADED = "DOWNLOADED"
FILE_TOUCHED = "FILE_TOUCHED"
PIP_INSTALL = 'PIP_INSTALL'
PKG_INSTALL = "PKG_INSTALL"
PKG_UPGRADE = "PKG_UPGRADE"
SYMLINK_MAKE = "SYMLINK_MAKE"


def trace_filename(root_dir, base_name):
    return sh.joinpths(root_dir, "%s.trace" % (base_name))


class TraceWriter(object):
    def __init__(self, trace_fn, break_if_there=True):
        self.trace_fn = trace_fn
        self.started = False
        self.break_if_there = break_if_there

    def trace(self, cmd, action=None):
        if action is None:
            action = ''
        if cmd is not None:
            sh.append_file(self.trace_fn, "%s - %s\n" % (cmd, action))

    def filename(self):
        return self.trace_fn

    def _start(self):
        if self.started:
            return
        else:
            trace_dirs = sh.mkdirslist(sh.dirname(self.trace_fn))
            sh.touch_file(self.trace_fn, die_if_there=self.break_if_there)
            self.started = True
            self.dirs_made(*trace_dirs)

    def symlink_made(self, link):
        self._start()
        self.trace(SYMLINK_MAKE, link)

    def download_happened(self, tgt, uri):
        self._start()
        what = dict()
        what['target'] = tgt
        what['from'] = uri
        self.trace(DOWNLOADED, json.dumps(what))

    def pip_installed(self, pip_info):
        self._start()
        self.trace(PIP_INSTALL, json.dumps(pip_info))

    def dirs_made(self, *dirs):
        self._start()
        for d in dirs:
            self.trace(DIR_MADE, d)

    def file_touched(self, fn):
        self._start()
        self.trace(FILE_TOUCHED, fn)

    def package_installed(self, pkg_name):
        self._start()
        self.trace(PKG_INSTALL, pkg_name)

    def package_upgraded(self, pkg_name):
        self._start()
        self.trace(PKG_UPGRADE, pkg_name)

    def app_started(self, name, info_fn, how):
        self._start()
        data = dict()
        data['name'] = name
        data['trace_fn'] = info_fn
        data['how'] = how
        self.trace(AP_STARTED, json.dumps(data))


class TraceReader(object):
    def __init__(self, trace_fn):
        self.trace_fn = trace_fn
        self.contents = None

    def filename(self):
        return self.trace_fn

    def _parse(self):
        fn = self.trace_fn
        if not sh.isfile(fn):
            msg = "No trace found at filename %s" % (fn)
            raise excp.NoTraceException(msg)
        contents = sh.load_file(fn)
        lines = contents.splitlines()
        accum = list()
        for line in lines:
            ep = self._split_line(line)
            if ep is None:
                continue
            accum.append(tuple(ep))
        return accum

    def read(self):
        if self.contents is None:
            self.contents = self._parse()
        return self.contents

    def _split_line(self, line):
        pieces = line.split("-", 1)
        if len(pieces) == 2:
            cmd = pieces[0].rstrip()
            action = pieces[1].lstrip()
            return (cmd, action)
        else:
            return None

    def exists(self):
        return sh.exists(self.trace_fn)

    def apps_started(self):
        lines = self.read()
        apps = list()
        for (cmd, action) in lines:
            if cmd == AP_STARTED and len(action):
                entry = json.loads(action)
                if type(entry) is dict:
                    apps.append((entry.get('name'), entry.get('trace_fn'), entry.get('how')))
        return apps

    def download_locations(self):
        lines = self.read()
        locations = list()
        for (cmd, action) in lines:
            if cmd == DOWNLOADED and len(action):
                entry = json.loads(action)
                if type(entry) is dict:
                    locations.append((entry.get('target'), entry.get('uri')))
        return locations

    def _sort_paths(self, pths):
        # Ensure in correct order (ie /tmp is before /)
        pths = list(set(pths))
        pths.sort()
        pths.reverse()
        return pths

    def files_touched(self):
        lines = self.read()
        files = list()
        for (cmd, action) in lines:
            if cmd == FILE_TOUCHED and len(action):
                files.append(action)
        return self._sort_paths(files)

    def dirs_made(self):
        lines = self.read()
        dirs = list()
        for (cmd, action) in lines:
            if cmd == DIR_MADE and len(action):
                dirs.append(action)
        return self._sort_paths(dirs)

    def symlinks_made(self):
        lines = self.read()
        links = list()
        for (cmd, action) in lines:
            if cmd == SYMLINK_MAKE and len(action):
                links.append(action)
        return links

    def pips_installed(self):
        lines = self.read()
        pips_installed = list()
        pip_list = list()
        for (cmd, action) in lines:
            if cmd == PIP_INSTALL and len(action):
                pip_list.append(action)
        for pip_data in pip_list:
            pip_info_full = json.loads(pip_data)
            if type(pip_info_full) is dict:
                pips_installed.append(pip_info_full)
        return pips_installed

    def packages_installed(self):
        lines = self.read()
        pkg_list = list()
        for (cmd, action) in lines:
            if cmd == PKG_INSTALL and len(action):
                pkg_list.append(action)
        return pkg_list
