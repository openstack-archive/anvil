#!/usr/bin/env python

import os
import sys

possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))

if os.path.exists(os.path.join(possible_topdir,
                               'anvil',
                               '__init__.py')):
    sys.path.insert(0, possible_topdir)

if len(sys.argv) == 1:
    print(sys.argv[0] + " root-component")
    sys.exit(1)

from anvil import settings
from anvil import cfg
from anvil import utils
from anvil import pprint

interp = cfg.YamlInterpolator(settings.COMPONENT_CONF_DIR)
result = interp.extract(sys.argv[1])
pprint.pprint(result)
