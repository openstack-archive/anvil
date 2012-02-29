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
from devstack import log as logging
from devstack import runner as base
from devstack import settings
from devstack import shell as sh
from devstack import trace as tr
from devstack import utils

LOG = logging.getLogger("devstack.runners.upstart")

#my type
RUN_TYPE = settings.RUN_TYPE_UPSTART
TYPE = settings.RUN_TYPE_TYPE

#trace constants
UPSTART_TEMPL = "%s.upstart"
ARGS = "ARGS"
NAME = "NAME"

#upstart event namings
START_EVENT_SUFFIX = "_start"
STOP_EVENT_SUFFIX = "_stop"

#where upstart configs go
CONF_ROOT = "/etc/init"
CONF_EXT = ".conf"

#shared template
UPSTART_CONF_TMPL = 'upstart.conf'

#how we emit events to upstart
EMIT_BASE_CMD = ["/sbin/initctl", "emit"]


class UpstartRunner(base.RunnerBase):
    def __init__(self, cfg, component_name, trace_dir):
        base.RunnerBase.__init__(self, cfg, component_name, trace_dir)
        self.events = set()

    def stop(self, app_name):
        fn_name = UPSTART_TEMPL % (app_name)
        trace_fn = tr.trace_fn(self.trace_dir, fn_name)
        # Emit the start, keep track and only do one per component name
        component_event = self.component_name + STOP_EVENT_SUFFIX
        if component_event in self.events:
            LOG.debug("Already emitted event: %s" % (component_event))
        else:
            LOG.info("About to emit event: %s" % (component_event))
            cmd = EMIT_BASE_CMD + [component_event]
            sh.execute(*cmd, run_as_root=True)
            self.events.add(component_event)
        sh.unlink(trace_fn)

    def configure(self, app_name, runtime_info):
        LOG.debug("Configure called for app: %s" % (app_name))
        self._do_upstart_configure(app_name, runtime_info)
        return 1

    def _get_upstart_conf_params(self, app_pth, program_name, *program_args):
        params = dict()
        if self.cfg.getboolean('upstart', 'respawn'):
            params['RESPAWN'] = "respawn"
        else:
            params['RESPAWN'] = ""
        params['SHORT_NAME'] = program_name
        params['MADE_DATE'] = date.rcf8222date()
        params['START_EVENT'] = self.cfg.get('upstart', 'start_event')
        params['STOP_EVENT'] = self.cfg.get('upstart', 'stop_event')
        params['COMPONENT_START_EVENT'] = self.component_name + START_EVENT_SUFFIX
        params['COMPONENT_STOP_EVENT'] = self.component_name + STOP_EVENT_SUFFIX
        params['PROGRAM_NAME'] = app_pth
        params['AUTHOR'] = settings.PROG_NICE_NAME
        if program_args:
            escaped_args = list()
            for opt in program_args:
                LOG.debug("Current opt: %s" % (opt))
                escaped_args.append(sh.shellquote(opt))
            params['PROGRAM_OPTIONS'] = " ".join(escaped_args)
        else:
            params['PROGRAM_OPTIONS'] = ''
        return params

    def _do_upstart_configure(self, app_name, runtime_info):
        (app_pth, _, program_args) = runtime_info
        # TODO FIXME symlinks won't work. Need to copy the files there.
        # https://bugs.launchpad.net/upstart/+bug/665022
        cfg_fn = sh.joinpths(CONF_ROOT, app_name + CONF_EXT)
        if sh.isfile(cfg_fn):
            LOG.info("Upstart config file already exists: %s" % (cfg_fn))
            return
        LOG.debug("Loading upstart template to be used by: %s" % (cfg_fn))
        (_, contents) = utils.load_template('general', UPSTART_CONF_TMPL)
        params = self._get_upstart_conf_params(app_pth, app_name, *program_args)
        adjusted_contents = utils.param_replace(contents, params)
        LOG.debug("Generated up start config for %s: %s" % (app_name, adjusted_contents))
        with sh.Rooted(True):
            sh.write_file(cfg_fn, adjusted_contents)
            sh.chmod(cfg_fn, 0666)

    def _start(self, app_name, program, program_args):
        fn_name = UPSTART_TEMPL % (app_name)
        tracefn = tr.touch_trace(self.trace_dir, fn_name)
        runtrace = tr.Trace(tracefn)
        runtrace.trace(TYPE, RUN_TYPE)
        runtrace.trace(NAME, app_name)
        runtrace.trace(ARGS, json.dumps(program_args))
        # Emit the start, keep track and only do one per component name
        component_event = self.component_name + START_EVENT_SUFFIX
        if component_event in self.events:
            LOG.debug("Already emitted event: %s" % (component_event))
        else:
            LOG.info("About to emit event: %s" % (component_event))
            cmd = EMIT_BASE_CMD + [component_event]
            sh.execute(*cmd, run_as_root=True)
            self.events.add(component_event)
        return tracefn

    def start(self, app_name, runtime_info):
        (program, _, program_args) = runtime_info
        return self._start(app_name, program, program_args)
