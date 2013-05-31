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

import os

from anvil import cfg
from anvil import colorizer
from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.components import base
from anvil.components import base_install as binstall
from anvil.packaging.helpers import pip_helper

LOG = logging.getLogger(__name__)


class EmptyTestingComponent(base.Component):
    def run_tests(self):
        return


class PythonTestingComponent(base.Component):
    def __init__(self, *args, **kargs):
        base.Component.__init__(self, *args, **kargs)
        self.helper = pip_helper.Helper(self.distro)

    def _get_test_exclusions(self):
        return self.get_option('exclude_tests', default_value=[])

    def _use_run_tests(self):
        return True

    def _get_test_command(self):
        # See: http://docs.openstack.org/developer/nova/devref/unit_tests.html
        # And: http://wiki.openstack.org/ProjectTestingInterface
        app_dir = self.get_option('app_dir')
        if sh.isfile(sh.joinpths(app_dir, 'run_tests.sh')) and self._use_run_tests():
            cmd = [sh.joinpths(app_dir, 'run_tests.sh'), '-N']
            if not self._use_pep8():
                cmd.append('--no-pep8')
        else:
            # Assume tox is being used, which we can't use directly
            # since anvil doesn't really do venv stuff (its meant to avoid those...)
            cmd = ['nosetests']
        # See: $ man nosetests
        if self.get_bool_option("verbose", default_value=False):
            cmd.append('--nologcapture')
        for e in self._get_test_exclusions():
            cmd.append('--exclude=%s' % (e))
        xunit_fn = self.get_option("xunit_filename")
        if xunit_fn:
            cmd.append("--with-xunit")
            cmd.append("--xunit-file=%s" % (xunit_fn))
        return cmd

    def _use_pep8(self):
        # Seems like the varying versions are borking pep8 from working...
        i_sibling = self.siblings.get('install')
        # Check if whats installed actually matches
        pep8_wanted = None
        if isinstance(i_sibling, (binstall.PythonInstallComponent)):
            for p in i_sibling.pip_requires:
                req = p['requirement']
                if req.key == "pep8":
                    pep8_wanted = req
                    break
        if not pep8_wanted:
            # Doesn't matter since its not wanted anyway
            return True
        pep8_there = self.helper.get_installed('pep8')
        if not pep8_there:
            # Hard to use it if it isn't there...
            LOG.warn("Pep8 version mismatch, none is installed but %s is wanting %s",
                     self.name, pep8_wanted)
            return False
        if not (pep8_there == pep8_wanted):
            # Versions not matching, this is causes pep8 to puke when it doesn't need to
            # so skip it from running in the first place...
            LOG.warn("Pep8 version mismatch, installed is %s but %s is applying %s",
                     pep8_there, self.name, pep8_wanted)
            return False
        return self.get_bool_option('use_pep8', default_value=True)

    def _get_env(self):
        env_addons = {}
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
        cmd = self._get_test_command()
        env = self._get_env()
        with open(os.devnull, 'wb') as null_fh:
            if self.get_bool_option("verbose", default_value=False):
                null_fh = None
            try:
                sh.execute(cmd, stdout_fh=None, stderr_fh=null_fh, cwd=app_dir, env_overrides=env)
            except excp.ProcessExecutionError as e:
                if self.get_bool_option("ignore-test-failures", default_value=False):
                    LOG.warn("Ignoring test failure of component %s: %s", colorizer.quote(self.name), e)
                else:
                    raise e
