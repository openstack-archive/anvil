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

from anvil import constants
from anvil import date
from anvil import log as logging
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils

from anvil.runners import base

LOG = logging.getLogger(__name__)

# Trace constants
UPSTART_TEMPL = "%s.upstart"
ARGS = "ARGS"
NAME = "NAME"

# Upstart event namings
START_EVENT_SUFFIX = "_start"
STOP_EVENT_SUFFIX = "_stop"

# Where upstart configs go
CONF_ROOT = "/etc/init"
CONF_EXT = ".conf"

# Shared template
UPSTART_CONF_TMPL = 'upstart.conf'

# How we emit events to upstart
EMIT_BASE_CMD = ["/sbin/initctl", "emit"]


class UpstartRunner(base.Runner):
    def __init__(self, runtime):
        base.Runner.__init__(self, runtime)
        self.cfg = self.runtime.cfg
        self.name = self.runtime.name
        self.events = set()

    def stop(self, app_name):
        fn_name = UPSTART_TEMPL % (app_name)
        trace_fn = tr.trace_fn(self.runtime.get_option('trace_dir'), fn_name)
        # Emit the start, keep track and only do one per component name
        component_event = self.name + STOP_EVENT_SUFFIX
        if component_event in self.events:
            LOG.debug("Already emitted event: %r" % (component_event))
        else:
            LOG.debug("About to emit event: %r" % (component_event))
            cmd = EMIT_BASE_CMD + [component_event]
            sh.execute(*cmd, run_as_root=True)
            self.events.add(component_event)
        sh.unlink(trace_fn)

    def configure(self, app_name, app_pth, app_dir, opts):
        LOG.debug("Configure called for app: %r" % (app_name))
        self._do_upstart_configure(app_name, app_pth, app_dir, opts)
        return 1

    def _get_upstart_conf_params(self, app_pth, program_name, *program_args):
        params = dict()
        if self.cfg.getboolean('upstart', 'respawn'):
            params['RESPAWN'] = "respawn"
        else:
            params['RESPAWN'] = ""
        params['SHORT_NAME'] = program_name
        params['MADE_DATE'] = date.rcf8222date()
        params['START_EVENT'] = self.cfg.getdefaulted('upstart', 'start_event', 'all_os_start')
        params['STOP_EVENT'] = self.cfg.getdefaulted('upstart', 'stop_event', 'all_os_stop')
        params['COMPONENT_START_EVENT'] = self.name + START_EVENT_SUFFIX
        params['COMPONENT_STOP_EVENT'] = self.name + STOP_EVENT_SUFFIX
        params['PROGRAM_NAME'] = app_pth
        params['AUTHOR'] = constants.PROG_NAME
        if program_args:
            escaped_args = list()
            for opt in program_args:
                LOG.debug("Current opt: %s" % (opt))
                escaped_args.append(sh.shellquote(opt))
            params['PROGRAM_OPTIONS'] = " ".join(escaped_args)
        else:
            params['PROGRAM_OPTIONS'] = ''
        return params

    def _do_upstart_configure(self, app_name, app_pth, app_dir, program_args):
        # TODO FIXME symlinks won't work. Need to copy the files there.
        # https://bugs.launchpad.net/upstart/+bug/665022
        cfg_fn = sh.joinpths(CONF_ROOT, app_name + CONF_EXT)
        if sh.isfile(cfg_fn):
            LOG.debug("Upstart config file already exists: %r" % (cfg_fn))
            return
        LOG.debug("Loading upstart template to be used by: %r" % (cfg_fn))
        (_, contents) = utils.load_template('general', UPSTART_CONF_TMPL)
        params = self._get_upstart_conf_params(app_pth, app_name, *program_args)
        adjusted_contents = utils.param_replace(contents, params)
        LOG.debug("Generated up start config for %r: %s" % (app_name, adjusted_contents))
        with sh.Rooted(True):
            sh.write_file(cfg_fn, adjusted_contents)
            sh.chmod(cfg_fn, 0666)

    def _start(self, app_name, program, program_args):
        run_trace = tr.TraceWriter(tr.trace_fn(self.runtime.get_option('trace_dir'), UPSTART_TEMPL % (app_name)))
        run_trace.trace(NAME, app_name)
        run_trace.trace(ARGS, json.dumps(program_args))
        # Emit the start, keep track and only do one per component name
        component_event = self.name + START_EVENT_SUFFIX
        if component_event in self.events:
            LOG.debug("Already emitted event: %r" % (component_event))
        else:
            LOG.debug("About to emit event: %r" % (component_event))
            cmd = EMIT_BASE_CMD + [component_event]
            sh.execute(*cmd, run_as_root=True)
            self.events.add(component_event)
        return run_trace.filename()

    def start(self, app_name, app_pth, app_dir, opts):
        return self._start(app_name, app_pth, opts)
