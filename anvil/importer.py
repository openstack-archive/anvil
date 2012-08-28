# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#    Copyright (C) 2012 New Dream Network, LLC (DreamHost) All Rights Reserved.
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

from anvil import log as logging

LOG = logging.getLogger(__name__)


def construct_entry_point(fullname, *args, **kwargs):
    cls = import_entry_point(fullname)
    return cls(*args, **kwargs)


def partition(fullname):
    """
    The name should be in dotted.path:ClassName syntax.
    """
    if ':' not in fullname:
        raise ValueError('Invalid entry point specifier %r' % fullname)
    (module_name, _, classname) = fullname.partition(':')
    return (module_name, classname)


def import_entry_point(fullname):
    """
    Given a name import the class and return it.
    """
    (module_name, classname) = partition(fullname)
    try:
        module = __import__(module_name)
        for submodule in module_name.split('.')[1:]:
            module = getattr(module, submodule)
        cls = getattr(module, classname)
    except (ImportError, AttributeError, ValueError) as err:
        raise RuntimeError('Could not load entry point %s: %s' %
                           (fullname, err))
    return cls


def import_module(module_name):
    try:
        __import__(module_name)
        LOG.debug("Importing module: %s", module_name)
        return sys.modules.get(module_name, None)
    except ImportError as err:
        raise RuntimeError('Could not load module %s: %s' %
                           (module_name, err))
