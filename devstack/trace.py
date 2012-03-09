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

from devstack import date
from devstack import exceptions as excp
from devstack import shell as sh

#trace per line output and file extension formats
TRACE_FMT = "%s - %s\n"
TRACE_EXT = ".trace"

#common trace actions
CFG_WRITING_FILE = "CFG_WRITING_FILE"
SYMLINK_MAKE = "SYMLINK_MAKE"
PKG_INSTALL = "PKG_INSTALL"
PYTHON_INSTALL = "PYTHON_INSTALL"
DIR_MADE = "DIR_MADE"
FILE_TOUCHED = "FILE_TOUCHED"
DOWNLOADED = "DOWNLOADED"
AP_STARTED = "AP_STARTED"
PIP_INSTALL = 'PIP_INSTALL'

#trace file types
PY_TRACE = "python"
IN_TRACE = "install"
START_TRACE = "start"

#used to note version of trace
TRACE_VERSION = "TRACE_VERSION"
TRACE_VER = 0x1


def trace_fn(root_dir, name):
    return sh.joinpths(root_dir, name + TRACE_EXT)


class TraceWriter(object):
    def __init__(self, trace_filename):
        self.trace_fn = trace_filename
        self.started = False

    def trace(self, cmd, action=None):
        if action is None:
            action = date.rcf8222date()
        if cmd is not None:
            sh.append_file(self.trace_fn, TRACE_FMT % (cmd, action))

    def filename(self):
        return self.trace_fn

    def _start(self):
        if self.started:
            return
        else:
            trace_dirs = sh.mkdirslist(sh.dirname(self.trace_fn))
            sh.touch_file(self.trace_fn)
            self.trace(TRACE_VERSION, str(TRACE_VER))
            self.started = True
            self.dirs_made(*trace_dirs)

    def py_installed(self, name, where):
        self._start()
        what = dict()
        what['name'] = name
        what['where'] = where
        self.trace(PYTHON_INSTALL, json.dumps(what))

    def cfg_file_written(self, fn):
        self._start()
        self.trace(CFG_WRITING_FILE, fn)

    def symlink_made(self, link):
        self._start()
        self.trace(SYMLINK_MAKE, link)

    def download_happened(self, tgt, uri):
        self._start()
        what = dict()
        what['target'] = tgt
        what['from'] = uri
        self.trace(DOWNLOADED, json.dumps(what))

    def pip_installed(self, name, pip_info):
        self._start()
        what = dict()
        what['name'] = name
        what['pip_meta'] = pip_info
        self.trace(PIP_INSTALL, json.dumps(what))

    def dirs_made(self, *dirs):
        self._start()
        for d in dirs:
            self.trace(DIR_MADE, d)

    def file_touched(self, fn):
        self._start()
        self.trace(FILE_TOUCHED, fn)

    def package_installed(self, name, pkg_info):
        self._start()
        what = dict()
        what['name'] = name
        what['pkg_meta'] = pkg_info
        self.trace(PKG_INSTALL, json.dumps(what))

    def started_info(self, name, info_fn):
        self._start()
        data = dict()
        data['name'] = name
        data['trace_fn'] = info_fn
        self.trace(AP_STARTED, json.dumps(data))


class TraceReader(object):
    def __init__(self, trace_filename):
        self.trace_fn = trace_filename
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

    def py_listing(self):
        lines = self.read()
        py_entries = list()
        for (cmd, action) in lines:
            if cmd == PYTHON_INSTALL and len(action):
                entry = json.loads(action)
                if type(entry) is dict:
                    py_entries.append((entry.get("name"), entry.get("where")))
        return py_entries

    def download_locations(self):
        lines = self.read()
        locs = list()
        for (cmd, action) in lines:
            if cmd == DOWNLOADED and len(action):
                entry = json.loads(action)
                if type(entry) is dict:
                    locs.append(entry.get('target'))
        return locs

    def files_touched(self):
        lines = self.read()
        files = list()
        for (cmd, action) in lines:
            if cmd == FILE_TOUCHED and len(action):
                files.append(action)
        files = list(set(files))
        files.sort()
        return files

    def dirs_made(self):
        lines = self.read()
        dirs = list()
        for (cmd, action) in lines:
            if cmd == DIR_MADE and len(action):
                dirs.append(action)
        #ensure in ok order (ie /tmp is before /)
        dirs = list(set(dirs))
        dirs.sort()
        dirs.reverse()
        return dirs

    def apps_started(self):
        lines = self.read()
        app_info = list()
        for (cmd, action) in lines:
            if cmd == AP_STARTED and len(action):
                entry = json.loads(action)
                if type(entry) is dict:
                    app_info.append((entry.get('trace_fn'), entry.get('name')))
        return app_info

    def symlinks_made(self):
        lines = self.read()
        files = list()
        for (cmd, action) in lines:
            if cmd == SYMLINK_MAKE and len(action):
                files.append(action)
        #ensure in ok order (ie /tmp is before /)
        files.sort()
        files.reverse()
        return files

    def files_configured(self):
        lines = self.read()
        files = list()
        for (cmd, action) in lines:
            if cmd == CFG_WRITING_FILE and len(action):
                files.append(action)
        files = list(set(files))
        files.sort()
        return files

    def pips_installed(self):
        lines = self.read()
        pips_installed = dict()
        pip_list = list()
        for (cmd, action) in lines:
            if cmd == PIP_INSTALL and len(action):
                pip_list.append(action)
        for pip_data in pip_list:
            pip_info_full = json.loads(pip_data)
            if type(pip_info_full) is dict:
                name = pip_info_full.get('name')
                if name:
                    pips_installed[name] = pip_info_full.get('pip_meta')
        return pips_installed

    def packages_installed(self):
        lines = self.read()
        pkgs_installed = dict()
        pkg_list = list()
        for (cmd, action) in lines:
            if cmd == PKG_INSTALL and len(action):
                pkg_list.append(action)
        for pkg_data in pkg_list:
            pkg_info = json.loads(pkg_data)
            if type(pkg_info) is dict:
                name = pkg_info.get('name')
                if name:
                    pkgs_installed[name] = pkg_info.get('pkg_meta')
        return pkgs_installed
