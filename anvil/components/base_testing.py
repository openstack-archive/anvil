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
import tempfile

from anvil import cfg
from anvil import colorizer
from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import type_utils as tu
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

    def _get_test_command(self):
        # See: http://docs.openstack.org/developer/nova/devref/unit_tests.html
        # And: http://wiki.openstack.org/ProjectTestingInterface
        # And: https://wiki.openstack.org/wiki/Testr

        def execute(cmd, capture=False):
            if capture:
                return sh.execute(cmd, cwd=self.get_option('app_dir'),
                                  env_overrides=self._get_env())
            else:
                return sh.execute(cmd, cwd=self.get_option('app_dir'),
                                  env_overrides=self._get_env(),
                                  stdout_fh=sys.stdout, stderr_fh=sys.stdout)

        def run_testr():
            # See: https://testrepository.readthedocs.org
            #
            # NOTE(harlowja): it appears that testr doesn't seem to support all
            # the 'advanced' features (coverage?, verbosity, xunit) as
            # nose. Need to verify this...
            exclusions = self._get_test_exclusions()
            if exclusions:
                cmd = ['testr', 'list-tests', self.get_option('app_dir')]
                (stdout, _stderr) = execute(cmd, True)
                test_lines = []
                for line in stdout.splitlines():
                    excluded = False
                    for e in exclusions:
                        if e and line.endswith(e):
                            excluded = True
                            break
                    if not excluded:
                        test_lines.append(line)
                with tempfile.NamedTemporaryFile(suffix=".list") as fh:
                    fh.write("\n".join(test_lines))
                    fh.flush()
                    cmd = ['testr', 'run', '--load-list', fh.name, '--parallel']
                    execute(cmd)
            else:
                execute(['testr', 'run', '--parallel'])

        def run_nose():
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
            execute(cmd)

        if _using_testr(self.test_type, self.get_option('app_dir')):
            return run_testr
        else:
            # Assume nose will work then.
            return run_nose

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
        runner_func = self._get_test_runner()
        if not runner_func:
            LOG.warn("Unable to determine test runner for %s, can not run tests.",
                     colorizer.quote(self.name))
            return
        try:
            LOG.info("Running tests via: %s", tu.obj_name(runner_func))
            runner_func()
        except excp.ProcessExecutionError as e:
            if self.ignore_test_failures:
                LOG.warn("Ignoring test failure of component %s: %s", colorizer.quote(self.name), e)
            else:
                raise
