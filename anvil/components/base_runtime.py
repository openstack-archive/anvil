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
from anvil import log as logging
from anvil import shell as sh

from anvil.components import base

LOG = logging.getLogger(__name__)


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
        self.stop()
        return self.start()

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
        num_started = len(self.subsystems)

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


class ServiceRuntime(ProgramRuntime):
    def get_command(self, command, program):
        program = self.daemon_name(program)
        return [(arg if arg != "NAME" else program)
                for arg in self.distro.get_command("service", command)]

    def daemon_name(self, program):
        return program

    def start(self):
        amount = 0
        for program in self.applications:
            if not self.status_app(program):
                if self.start_app(program):
                    amount += 1
        return amount

    def start_app(self, program):
        LOG.info("Starting program %s under component %s.",
                 colorizer.quote(program), self.name)

        start_cmd = self.get_command("start", program)
        try:
            sh.execute(start_cmd, shell=True)
        except excp.ProcessExecutionError:
            LOG.error("Failed to start program %s under component %s.",
                 colorizer.quote(program), self.name)
            return False
        return True

    def stop(self):
        amount = 0
        for program in self.applications:
            if self.status_app(program):
                if self.stop_app(program):
                    amount += 1
        return amount

    def stop_app(self, program):
        LOG.info("Stopping program %s under component %s.",
                 colorizer.quote(program), self.name)
        stop_cmd = self.get_command("stop", program)
        try:
            sh.execute(stop_cmd, shell=True)
        except excp.ProcessExecutionError:
            LOG.error("Failed to stop program %s under component %s.",
                 colorizer.quote(program), self.name)
            return False
        return True

    def status_app(self, program):
        status_cmd = self.get_command("status", program)
        try:
            sh.execute(status_cmd, shell=True)
        except excp.ProcessExecutionError:
            return False
        return True

    def statii(self):
        # Get the investigators/runners which can be used
        # to actually do the status inquiry and attempt to perform said inquiry.
        statii = []
        for program in self.applications:
            status = (STATUS_STARTED
                      if self.status_app(program)
                      else STATUS_STOPPED)
            statii.append(ProgramStatus(name=program,
                                        status=status,
                                        details={}))
        return statii


class OpenStackRuntime(ServiceRuntime):
    @property
    def applications(self):
        return self.subsystem_names()

    def daemon_name(self, program):
        return "openstack-%s-%s" % (self.name, program)
