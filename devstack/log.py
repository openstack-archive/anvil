# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#
#    Copyright 2011 OpenStack LLC.
#    All Rights Reserved.
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
import logging
import pprint

from logging.handlers import SysLogHandler
from logging.handlers import WatchedFileHandler

# a list of things we want to replicate from logging levels
CRITICAL = logging.CRITICAL
FATAL = logging.FATAL
ERROR = logging.ERROR
WARNING = logging.WARNING
WARN = logging.WARN
INFO = logging.INFO
DEBUG = logging.DEBUG
NOTSET = logging.NOTSET

# our new audit level
# http://docs.python.org/howto/logging.html#logging-levels
logging.AUDIT = logging.DEBUG + 1
logging.addLevelName(logging.AUDIT, 'AUDIT')
AUDIT = logging.AUDIT

# methods
debug = logging.debug
info = logging.info
warning = logging.warning
warn = logging.warn
error = logging.error
exception = logging.exception
critical = logging.critical
log = logging.log

# classes
root = logging.root
Formatter = logging.Formatter

# handlers
StreamHandler = logging.StreamHandler
WatchedFileHandler = WatchedFileHandler
SysLogHandler = SysLogHandler


class AuditAdapter(logging.LoggerAdapter):
    warn = logging.LoggerAdapter.warning

    def __init__(self, logger):
        logging.LoggerAdapter.__init__(self)
        self.logger = logger

    def audit(self, msg, *args, **kwargs):
        self.log(logging.AUDIT, msg, *args, **kwargs)

    def process(self, msg, kwargs):
        return msg, kwargs


def getLogger(name='devstack'):
    return AuditAdapter(logging.getLogger(name))


def log_debug(f):
    @functools.wraps(f)
    def wrapper(*args, **kw):
        if root.isEnabledFor(debug):
            logging.debug('%s(%s, %s) ->', f.func_name, str(args), str(kw))
        rv = f(*args, **kw)
        if root.isEnabledFor(debug):
            logging.debug(pprint.pformat(rv, indent=2))
            logging.debug('')
        return rv
    return wrapper
