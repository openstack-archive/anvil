#!/usr/bin/python

## Tool to run the nova config generating code and spit out a dummy
## version.  Useful for testing that code in isolation.

import os
import sys
import tempfile
import atexit

possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))

if os.path.exists(os.path.join(possible_topdir,
                               'anvil',
                               '__init__.py')):
    sys.path.insert(0, possible_topdir)

from anvil.components.helpers.nova import ConfConfigurator
from anvil.trace import TraceWriter

from anvil import utils
from anvil import shell as sh

DUMMY_FILE = tempfile.mktemp()


def at_exit_cleaner():
    sh.unlink(DUMMY_FILE)

atexit.register(at_exit_cleaner)


def make_fakey(all_opts, last='dummy'):
    src = {}
    tmp = src
    last_opt = all_opts[-1]
    for opt in all_opts[0:-1]:
        tmp[opt] = {}
        tmp = tmp[opt]
    tmp[last_opt] = last
    return src


class DummyInstaller(object):
    def get_option(self, option, *options, **kwargs):
        if option == 'db':
            src = {
                option: {
                    'host': 'localhost',
                    'port': 3306,
                    'type': 'mysql',
                    'user': 'root'
                },
            }
        elif option == 'ip':
            return utils.get_host_ip()
        elif utils.has_any(option, 'extra_flags', 'extra_opts', 'instances_path'):
            return ''
        else:
            # Make a fake dictionary hierachy
            src = make_fakey([option] + list(options))
        return utils.get_deep(src, [option] + list(options))

    def get_bool_option(self, option, *options, **kwargs):
        return False

    def get_password(self, option, *options, **kwargs):
        return "forbinus"

    def target_config(self, config_fn):
        return None

    def __init__(self):
        self.tracewriter = TraceWriter(DUMMY_FILE)



d = DummyInstaller()
c = ConfConfigurator(d)
print c.generate("foo.conf")
