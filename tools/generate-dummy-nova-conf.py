#!/usr/bin/python

## Tool to run the nova config generating code and spit out a dummy
## version.  Useful for testing that code in isolation.

import os
import sys

possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))

if os.path.exists(os.path.join(possible_topdir,
                               'anvil',
                               '__init__.py')):
    sys.path.insert(0, possible_topdir)

from  anvil.components.helpers.nova import ConfConfigurator
from  anvil.trace import TraceWriter

class DummyInstaller(object):
    def get_option(self, option, *options, **kwargs):
        if option == 'db':
            return {'host': 'localhost',
                    'port': 3306,
                    'type': 'mysql',
                    'user': 'root'}
        return "dummy"

    def get_bool_option(self, option, *options, **kwargs):
        return False

    def get_password(self, option, *options, **kwargs):
        return "forbinus"

    def target_config(self, config_fn):
        return None

    def __init__(self):
        self.tracewriter = TraceWriter("dummy-config-trace")

d = DummyInstaller()
c = ConfConfigurator(d)
print c.generate("foo.conf")
