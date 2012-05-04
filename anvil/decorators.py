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

import functools
import pprint

from anvil import log as logging

# Very useful example ones...
# See: http://wiki.python.org/moin/PythonDecoratorLibrary

LOG = logging.getLogger(__name__)


def log_debug(f):
    @functools.wraps(f)
    def wrapper(*args, **kargs):
        LOG.debug('%s(%s, %s) ->', f.func_name, str(args), str(kargs))
        rv = f(*args, **kargs)
        LOG.debug("<- %s" % (pprint.pformat(rv, indent=2)))
        return rv
    return wrapper
