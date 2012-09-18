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

from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from contextlib import contextmanager

LOG = logging.getLogger(__name__)


class PhaseRecorder(object):
    def __init__(self, fn):
        self.fn = fn
        self.state = None

    def _format_contents(self, contents):
        return utils.prettify_yaml(contents)

    @contextmanager
    def mark(self, what):
        contents = self.list_phases()
        contents[what] = utils.iso8601()
        yield what
        sh.write_file(self.fn, self._format_contents(contents))

    def unmark(self, what):
        contents = self.list_phases()
        contents.pop(what, None)
        sh.write_file(self.fn, self._format_contents(contents))

    def __contains__(self, what):
        phases = self.list_phases()
        if what in phases:
            return True
        return False

    def list_phases(self):
        if self.state is not None:
            return self.state
        state = {}
        # Shell not used to avoid dry-run capturing
        try:
            with open(self.fn, 'r') as fh:
                state = utils.load_yaml_text(fh.read())
                if not isinstance(state, (dict)):
                    raise TypeError("Phase file %s expected dictionary root type" % (self.fn))
        except IOError:
            pass
        self.state = state
        return self.state


class NullPhaseRecorder(object):
    def __init__(self):
        pass

    @contextmanager
    def mark(self, what):
        yield what

    def list_phases(self):
        return {}

    def unmark(self, what):
        pass

    def __contains__(self, what):
        return False
