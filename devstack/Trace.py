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

import os.path
import json

import Util
from Util import (rcf8222date)

import Shell
from Shell import (touch_file, append_file, joinpths, load_file, mkdirslist)

TRACE_FMT = "%s - %s\n"
TRACE_EXT = ".trace"

#common trace actions
CFG_WRITING_FILE = "CFG_WRITING_FILE"
PKG_INSTALL = "PKG_INSTALL"
PYTHON_INSTALL = "PYTHON_INSTALL"
DIR_MADE = "DIR_MADE"
FILE_TOUCHED = "FILE_TOUCHED"
DOWNLOADED = "DOWNLOADED"
AP_STARTED = "AP_STARTED"

#trace file types
PY_TRACE = "python"
IN_TRACE = "install"
START_TRACE = "start"

#used to note version of trace
TRACE_VERSION = "TRACE_VERSION"
TRACE_VER = 0x1


class Trace():
    def __init__(self, tracefn):
        self.tracefn = tracefn

    def fn(self):
        return self.tracefn

    def trace(self, cmd, action=None):
        if(action == None):
            action = rcf8222date()
        line = TRACE_FMT % (cmd, action)
        append_file(self.tracefn, line)


class TraceWriter():
    def __init__(self, root, name):
        self.tracer = None
        self.root = root
        self.name = name
        self.started = False

    def _start(self):
        if(self.started):
            return
        else:
            dirs = mkdirslist(self.root)
            fn = touch_trace(self.root, self.name)
            self.tracer = Trace(fn)
            cmd = TRACE_VERSION
            action = str(TRACE_VER)
            self.tracer.trace(cmd, action)
            cmd = DIR_MADE
            for d in dirs:
                action = d
                self.tracer.trace(cmd, action)
            self.started = True

    def py_install(self, where):
        self._start()
        cmd = PYTHON_INSTALL
        action = where
        self.tracer.trace(cmd, action)

    def cfg_write(self, cfgfile):
        self._start()
        cmd = CFG_WRITING_FILE
        action = cfgfile
        self.tracer.trace(cmd, action)

    def downloaded(self, tgt, fromwhere):
        self._start()
        cmd = DOWNLOADED
        action = dict()
        action['target'] = tgt
        action['from'] = fromwhere
        store = json.dumps(action)
        self.tracer.trace(cmd, store)

    def dir_made(self, *dirs):
        self._start()
        cmd = DIR_MADE
        for d in dirs:
            action = d
            self.tracer.trace(cmd, action)

    def file_touched(self, fn):
        self._start()
        cmd = FILE_TOUCHED
        action = fn
        self.tracer.trace(cmd, action)

    def package_install(self, name, removeable, version):
        self._start()
        pkgmeta = dict()
        pkgmeta['name'] = name
        pkgmeta['removable'] = removeable
        pkgmeta['version'] = version
        tracedata = json.dumps(pkgmeta)
        cmd = PKG_INSTALL
        action = tracedata
        self.tracer.trace(cmd, action)

    def started_info(self, name, info_fn):
        self._start()
        cmd = AP_STARTED
        out = dict()
        out['name'] = name
        out['trace_fn'] = info_fn
        action = json.dumps(out)
        self.tracer.trace(cmd, action)


class TraceReader():
    def __init__(self, root, name):
        self.root = root
        self.name = name
        self.trace_fn = trace_fn(root, name)

    def _readpy(self):
        lines = self._read()
        pyfn = None
        pylines = list()
        for (cmd, action) in lines:
            if(cmd == PYTHON_INSTALL and len(action)):
                pyfn = action
                break
        if(pyfn != None):
            lines = load_file(pyfn).splitlines()
            pylines = lines
        return pylines

    def _read(self):
        return parse_name(self.root, self.name)

    def py_listing(self):
        return self._readpy()

    def files_touched(self):
        lines = self._read()
        files = list()
        for (cmd, action) in lines:
            if(cmd == FILE_TOUCHED and len(action)):
                files.append(action)
        #ensure no dups
        files = list(set(files))
        files.sort()
        return files

    def dirs_made(self):
        lines = self._read()
        dirs = list()
        for (cmd, action) in lines:
            if(cmd == DIR_MADE and len(action)):
                dirs.append(action)
        #ensure not dups
        dirs = list(set(dirs))
        #ensure in ok order (ie /tmp is before /)
        dirs.sort()
        dirs.reverse()
        return dirs

    def apps_started(self):
        lines = self._read()
        files = list()
        for (cmd, action) in lines:
            if(cmd == AP_STARTED and len(action)):
                jdec = json.loads(action)
                if(type(jdec) is dict):
                    files.append(jdec)
        return files

    def files_configured(self):
        lines = self._read()
        files = list()
        for (cmd, action) in lines:
            if(cmd == CFG_WRITING_FILE and len(action)):
                files.append(action)
        #ensure not dups
        files = list(set(files))
        files.sort()
        return files

    def packages_installed(self):
        lines = self._read()
        pkgsinstalled = dict()
        actions = list()
        for (cmd, action) in lines:
            if(cmd == PKG_INSTALL and len(action)):
                actions.append(action)
        for action in actions:
            pv = json.loads(action)
            if(type(pv) is dict):
                name = pv.get("name", "")
                remove = pv.get("removable", True)
                version = pv.get("version", "")
                if(remove and len(name)):
                    if(len(version)):
                        pkgsinstalled[name] = {"version": version}
                    else:
                        pkgsinstalled[name] = {}
        return pkgsinstalled


def trace_fn(rootdir, name):
    fullname = name + TRACE_EXT
    tracefn = joinpths(rootdir, fullname)
    return tracefn


def touch_trace(rootdir, name):
    tracefn = trace_fn(rootdir, name)
    touch_file(tracefn)
    return tracefn


def split_line(line):
    pieces = line.split("-", 1)
    if(len(pieces) == 2):
        cmd = pieces[0].rstrip()
        action = pieces[1].lstrip()
        return (cmd, action)
    else:
        return None


def read(rootdir, name):
    pth = trace_fn(rootdir, name)
    contents = load_file(pth)
    lines = contents.splitlines()
    return lines


def parse_fn(fn):
    contents = load_file(fn)
    lines = contents.splitlines()
    accum = list()
    for line in lines:
        ep = split_line(line)
        if(ep == None):
            continue
        accum.append(tuple(ep))
    return accum


def parse_name(rootdir, name):
    return parse_fn(trace_fn(rootdir, name))
