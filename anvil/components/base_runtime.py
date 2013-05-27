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

from anvil import colorizer
from anvil import exceptions as excp
from anvil import importer
from anvil import log as logging
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils

from anvil.components import base

LOG = logging.getLogger(__name__)

DEFAULT_RUNNER = 'anvil.runners.fork:ForkRunner'

####
#### STATUS CONSTANTS
####
STATUS_INSTALLED = 'installed'
STATUS_STARTED = "started"
STATUS_STOPPED = "stopped"
STATUS_UNKNOWN = "unknown"


class ProgramStatus(object):
    def __init__(self, status, name=None, details=''):
        self.name = name
        self.status = status
        self.details = details


class Program(object):
    def __init__(self, name, path=None, working_dir=None, argv=None):
        self.name = name
        if path is None:
            self.path = name
        else:
            self.path = path
        self.working_dir = working_dir
        if argv is None:
            self.argv = tuple()
        else:
            self.argv = tuple(argv)

    def __str__(self):
        what = str(self.name)
        if self.path:
            what += " (%s)" % (self.path)
        return what


class ProgramRuntime(base.Component):
    @property
    def applications(self):
        # A list of applications since a single component sometimes
        # has a list of programs to start (ie nova) instead of a single application (ie the db)
        return []

    def restart(self):
        # How many applications restarted
        return 0

    def post_start(self):
        pass

    def pre_start(self):
        pass

    def statii(self):
        # A list of statuses since a single component sometimes
        # has a list of programs to report on (ie nova) instead of a single application (ie the db)
        return []

    def start(self):
        # How many applications started
        return 0

    def stop(self):
        # How many applications stopped
        return 0

    # TODO(harlowja): seems like this could be a mixin?
    def wait_active(self, between_wait=1, max_attempts=5):
        # Attempt to wait until all potentially started applications
        # are actually started (for whatever defintion of started is applicable)
        # for up to a given amount of attempts and wait time between attempts.
        num_started = len(self.applications)
        if not num_started:
            raise excp.StatusException("No %r programs started, can not wait for them to become active..." % (self.name))

        def waiter(try_num):
            LOG.info("Waiting %s seconds for component %s programs to start.", between_wait, colorizer.quote(self.name))
            LOG.info("Please wait...")
            sh.sleep(between_wait)

        for i in range(0, max_attempts):
            statii = self.statii()
            if len(statii) >= num_started:  # >= if someone reports more than started...
                not_worked = []
                for p in statii:
                    if p.status != STATUS_STARTED:
                        not_worked.append(p)
                if len(not_worked) == 0:
                    return
            else:
                # Eck less applications were found with status then what were started!
                LOG.warn("%s less applications reported status than were actually started!",
                         num_started - len(statii))
            waiter(i + 1)

        tot_time = max(0, (between_wait * max_attempts))
        raise excp.StatusException("Failed waiting %s seconds for component %r programs to become active..."
                                   % (tot_time, self.name))


class EmptyRuntime(ProgramRuntime):
    pass


class PythonRuntime(ProgramRuntime):
    def __init__(self, *args, **kargs):
        ProgramRuntime.__init__(self, *args, **kargs)
        start_trace = tr.trace_filename(self.get_option('trace_dir'), 'start')
        self.tracewriter = tr.TraceWriter(start_trace, break_if_there=True)
        self.tracereader = tr.TraceReader(start_trace)

    def app_params(self, program):
        params = dict(self.params)
        if program and program.name:
            params['APP_NAME'] = str(program.name)
        return params

    def start(self):
        # Perform a check just to make sure said programs aren't already started and bail out
        # so that it we don't unintentionally start new ones and thus causing confusion for all
        # involved...
        what_may_already_be_started = []
        try:
            what_may_already_be_started = self.tracereader.apps_started()
        except excp.NoTraceException:
            pass
        if what_may_already_be_started:
            msg = "%s programs of component %s may already be running, did you forget to stop those?"
            raise excp.StartException(msg % (len(what_may_already_be_started), self.name))

        # Select how we are going to start it and get on with the show...
        runner_entry_point = self.get_option("run_type", default_value=DEFAULT_RUNNER)
        starter_args = [self, runner_entry_point]
        starter = importer.construct_entry_point(runner_entry_point, *starter_args)
        amount_started = 0
        for program in self.applications:
            self._start_app(program, starter)
            amount_started += 1
        return amount_started

    def _start_app(self, program, starter):
        app_working_dir = program.working_dir
        if not app_working_dir:
            app_working_dir = self.get_option('app_dir')

        # Un-templatize whatever argv (program options) the program has specified
        # with whatever program params were retrieved to create the 'real' set
        # of program options (if applicable)
        app_params = self.app_params(program)
        if app_params:
            app_argv = [utils.expand_template(arg, app_params) for arg in program.argv]
        else:
            app_argv = program.argv
        LOG.debug("Starting %r using a %r", program.name, starter)

        # TODO(harlowja): clean this function params up (should just take a program)
        details_path = starter.start(program.name,
                                     app_pth=program.path,
                                     app_dir=app_working_dir,
                                     opts=app_argv)

        # This trace is used to locate details about what/how to stop
        LOG.info("Started program %s under component %s.", colorizer.quote(program.name), self.name)
        self.tracewriter.app_started(program.name, details_path, starter.name)

    def _locate_investigators(self, applications_started):
        # Recreate the runners that can be used to dive deeper into the applications list
        # that was started (a 3 tuple of (name, trace, who_started)).
        investigators_created = {}
        to_investigate = []
        for (name, _trace, who_started) in applications_started:
            investigator = investigators_created.get(who_started)
            if investigator is None:
                try:
                    investigator_args = [self, who_started]
                    investigator = importer.construct_entry_point(who_started, *investigator_args)
                    investigators_created[who_started] = investigator
                except RuntimeError as e:
                    LOG.warn("Could not load class %s which should be used to investigate %s: %s",
                             colorizer.quote(who_started), colorizer.quote(name), e)
                    continue
            to_investigate.append((name, investigator))
        return to_investigate

    def stop(self):
        # Anything to stop in the first place??
        what_was_started = []
        try:
            what_was_started = self.tracereader.apps_started()
        except excp.NoTraceException:
            pass
        if not what_was_started:
            return 0

        # Get the investigators/runners which can be used
        # to actually do the stopping and attempt to perform said stop.
        applications_stopped = []
        for (name, handler) in self._locate_investigators(what_was_started):
            handler.stop(name)
            applications_stopped.append(name)
        if applications_stopped:
            utils.log_iterable(applications_stopped,
                               header="Stopped %s programs started under %s component" % (len(applications_stopped), self.name),
                               logger=LOG)

        # Only if we stopped the amount which was supposedly started can
        # we actually remove the trace where those applications have been
        # marked as started in (ie the connection back to how they were started)
        if len(applications_stopped) < len(what_was_started):
            diff = len(what_was_started) - len(applications_stopped)
            LOG.warn(("%s less applications were stopped than were started, please check out %s"
                      " to stop these program manually."), diff, colorizer.quote(self.tracereader.filename(), quote_color='yellow'))
        else:
            sh.unlink(self.tracereader.filename())

        return len(applications_stopped)

    def statii(self):
        # Anything to get status on in the first place??
        what_was_started = []
        try:
            what_was_started = self.tracereader.apps_started()
        except excp.NoTraceException:
            pass
        if not what_was_started:
            return []

        # Get the investigators/runners which can be used
        # to actually do the status inquiry and attempt to perform said inquiry.
        statii = []
        for (name, handler) in self._locate_investigators(what_was_started):
            (status, details) = handler.status(name)
            statii.append(ProgramStatus(name=name,
                                        status=status,
                                        details=details))
        return statii
