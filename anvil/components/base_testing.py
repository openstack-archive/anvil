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

import sys

from anvil import cfg
from anvil import colorizer
from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.components import base
from anvil.packaging.helpers import pip_helper

LOG = logging.getLogger(__name__)


# Environment to run tests
DEFAULT_ENV = {
    'NOSE_WITH_OPENSTACK': '1',
    'NOSE_OPENSTACK_RED': '0.05',
    'NOSE_OPENSTACK_YELLOW': '0.025',
    'NOSE_OPENSTACK_SHOW_ELAPSED': '1',
}


def _using_testr(test_type, app_dir):
    if test_type == 'testr':
        return True
    for i in ['.testr.conf', '.testrepository']:
        if sh.exists(sh.joinpths(app_dir, i)):
            return True
    return False


class EmptyTestingComponent(base.Component):
    def run_tests(self):
        return


class PythonTestingComponent(base.Component):
    def __init__(self, *args, **kargs):
        base.Component.__init__(self, *args, **kargs)
        self.helper = pip_helper.Helper()
        self.test_type = self.get_option('test_type', default_value='').lower().strip()
        self.ignore_test_failures = kargs.get('ignore_test_failures', False)

    def _get_test_exclusions(self):
        return self.get_option('exclude_tests', default_value=[])

    def _get_test_dir_exclusions(self):
        return self.get_option('exclude_tests_dir', default_value=[])

    def _get_pre_test_command(self):
        app_dir = self.get_option('app_dir')
        if (_using_testr(self.test_type, app_dir) and
            not sh.isdir(sh.joinpths(app_dir, '.testrepository'))):
            return ['testr', 'init']
        return None

    def _get_test_command(self):
        # See: http://docs.openstack.org/developer/nova/devref/unit_tests.html
        # And: http://wiki.openstack.org/ProjectTestingInterface
        # And: https://wiki.openstack.org/wiki/Testr

        def get_testr_cmd():
            # See: https://testrepository.readthedocs.org
            #
            # NOTE(harlowja): it appears that testr doesn't seem to support all
            # the 'advanced' features (exclusion, coverage?, verbosity, xunit) as
            # nose. Need to verify this...
            return ['testr', 'run', '--parallel']

        def get_nose_cmd():
            # See: $ man nosetests
            cmd = ['coverage', 'run', '/usr/bin/nosetests']
            if not colorizer.color_enabled():
                cmd.append('--openstack-nocolor')
            else:
                cmd.append('--openstack-color')
            if self.get_bool_option("verbose", default_value=True):
                cmd.append('--verbosity=2')
                cmd.append('--detailed-errors')
            else:
                cmd.append('--verbosity=1')
                cmd.append('--openstack-num-slow=0')
            for e in self._get_test_exclusions():
                cmd.append('--exclude=%s' % (e))
            for e in self._get_test_dir_exclusions():
                cmd.append('--exclude-dir=%s' % (e))
            xunit_fn = self.get_option("xunit_filename")
            if xunit_fn:
                cmd.append("--with-xunit")
                cmd.append("--xunit-file=%s" % (xunit_fn))
            return cmd

        if _using_testr(self.test_type, self.get_option('app_dir')):
            return get_testr_cmd()
        else:
            # Assume nose will work then.
            return get_nose_cmd()

    def _get_env(self):
        env_addons = DEFAULT_ENV.copy()
        tox_fn = sh.joinpths(self.get_option('app_dir'), 'tox.ini')
        if sh.isfile(tox_fn):
            # Suck out some settings from the tox file
            try:
                tox_cfg = cfg.BuiltinConfigParser(fns=[tox_fn])
                env_values = tox_cfg.get('testenv', 'setenv') or ''
                for env_line in env_values.splitlines():
                    env_line = env_line.strip()
                    env_line = env_line.split("#")[0].strip()
                    if not env_line:
                        continue
                    env_entry = env_line.split('=', 1)
                    if len(env_entry) == 2:
                        (name, value) = env_entry
                        name = name.strip()
                        value = value.strip()
                        if name.lower() != 'virtual_env':
                            env_addons[name] = value
                if env_addons:
                    LOG.debug("From %s we read in %s environment settings:", tox_fn, len(env_addons))
                    utils.log_object(env_addons, logger=LOG, level=logging.DEBUG)
            except IOError:
                pass
        return env_addons

    def run_tests(self):
        app_dir = self.get_option('app_dir')
        if not sh.isdir(app_dir):
            LOG.warn("Unable to find application directory at %s, can not run %s tests.",
                     colorizer.quote(app_dir), colorizer.quote(self.name))
            return
        pre_cmd = self._get_pre_test_command()
        cmd = self._get_test_command()
        if not cmd:
            LOG.warn("Unable to determine test command for %s, can not run tests.",
                     colorizer.quote(self.name))
            return
        env = self._get_env()
        try:
            if pre_cmd:
                LOG.info("Running test setup via: %s",
                         utils.truncate_text(" ".join(pre_cmd), 80))
                sh.execute(pre_cmd, stdout_fh=sys.stdout, stderr_fh=sys.stdout,
                           cwd=app_dir, env_overrides=env)
            LOG.info("Running tests via: %s",
                     utils.truncate_text(" ".join(cmd), 80))
            sh.execute(cmd, stdout_fh=sys.stdout, stderr_fh=sys.stdout,
                       cwd=app_dir, env_overrides=env)
        except excp.ProcessExecutionError as e:
            if self.ignore_test_failures:
                LOG.warn("Ignoring test failure of component %s: %s", colorizer.quote(self.name), e)
            else:
                raise
