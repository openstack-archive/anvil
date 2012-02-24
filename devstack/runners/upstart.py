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

#where upstart configs go
CONF_ROOT = "/etc/init"
CONF_EXT = ".conf"

#shared template
UPSTART_CONF_TMPL = 'upstart.conf'


class UpstartRunner(object):
    def __init__(self, cfg):
        self.cfg = cfg

    def stop(self, name, *args, **kargs):
        msg = "Not implemented yet"
        raise NotImplementedError(msg)

    def _get_upstart_conf_params(self, name, program_name, *program_args):
        params = dict()
        if self.cfg.getboolean('upstart', 'respawn'):
            params['RESPAWN'] = "respawn"
        else:
            params['RESPAWN'] = ""
        params['SHORT_NAME'] = name
        params['MADE_DATE'] = date.rcf8222date()
        params['START_EVENT'] = self.cfg.get('upstart', 'start_event')
        params['STOP_EVENT'] = self.cfg.get('upstart', 'stop_event')
        params['PROGRAM_NAME'] = sh.shellquote(program_name)
        params['AUTHOR'] = settings.PROG_NICE_NAME
        if program_args:
            escaped_args = list()
            for opt in program_args:
                escaped_args.append(sh.shellquote(opt))
            params['PROGRAM_OPTIONS'] = " ".join(escaped_args)
        else:
            params['PROGRAM_OPTIONS'] = ''
        return params

    def _do_upstart_configure(self, name, program_name, *program_args):
        root_fn = name + CONF_EXT
        # TODO FIXME symlinks won't work. Need to copy the files there.
        # https://bugs.launchpad.net/upstart/+bug/665022
        cfg_fn = sh.joinpths(CONF_ROOT, root_fn)
        if sh.isfile(cfg_fn):
            return
        LOG.debug("Loading upstart template to be used by: %s" % (cfg_fn))
        (_, contents) = utils.load_template('general', UPSTART_CONF_TMPL)
        params = self._get_upstart_conf_params(name, program_name, *program_args)
        adjusted_contents = utils.param_replace(contents, params)
        LOG.debug("Generated up start config for %s: %s" % (name, adjusted_contents))
        with sh.Rooted(True):
            sh.write_file(cfg_fn, adjusted_contents)
            sh.chmod(cfg_fn, 0666)

    def _start(self, name, program, *program_args, **kargs):
        tracedir = kargs["trace_dir"]
        fn_name = UPSTART_TEMPL % (name)
        tracefn = tr.touch_trace(tracedir, fn_name)
        runtrace = tr.Trace(tracefn)
        runtrace.trace(TYPE, RUN_TYPE)
        runtrace.trace(NAME, name)
        runtrace.trace(ARGS, json.dumps(program_args))
        return tracefn

    def start(self, name, program, *program_args, **kargs):
        msg = "Not implemented yet"
        raise NotImplementedError(msg)
