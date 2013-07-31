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

# pylint: disable=C0103

import logging
import sys

from anvil import colorizer


# A list of things we want to replicate from logging levels
CRITICAL = logging.CRITICAL
FATAL = logging.FATAL
ERROR = logging.ERROR
WARNING = logging.WARNING
WARN = logging.WARN
INFO = logging.INFO
DEBUG = logging.DEBUG
NOTSET = logging.NOTSET

# Methods
debug = logging.debug
info = logging.info
warning = logging.warning
warn = logging.warn
error = logging.error
exception = logging.exception
critical = logging.critical
log = logging.log

# Nice translator
getLevelName = logging.getLevelName

# Classes
root = logging.root
Formatter = logging.Formatter

# Handlers
StreamHandler = logging.StreamHandler


class TermFormatter(logging.Formatter):

    COLOR_MAP = {
        logging.DEBUG: 'blue',
        logging.INFO: 'cyan',
        logging.WARNING: 'yellow',
        logging.ERROR: 'red',
        logging.CRITICAL: 'red',
    }
    MSG_COLORS = {
        logging.CRITICAL: 'red',
    }

    def __init__(self, reg_fmt=None, date_format=None):
        logging.Formatter.__init__(self, reg_fmt, date_format)

    def _format_msg(self, lvl, msg):
        color_to_be = self.MSG_COLORS.get(lvl)
        if color_to_be:
            return colorizer.color(msg, color_to_be, bold=True)
        else:
            return msg

    def _format_lvl(self, lvl, lvl_name):
        color_to_be = self.COLOR_MAP.get(lvl)
        if color_to_be:
            return colorizer.color(lvl_name, color_to_be)
        else:
            return lvl_name

    def format(self, record):
        record.levelname = self._format_lvl(record.levelno, record.levelname)
        record.msg = self._format_msg(record.levelno, record.msg)
        return logging.Formatter.format(self, record)


class TermAdapter(logging.LoggerAdapter):

    warn = logging.LoggerAdapter.warning

    def __init__(self, logger):
        logging.LoggerAdapter.__init__(self, logger, dict())


def setupLogging(log_level, format='%(levelname)s: @%(name)s : %(message)s'):
    root_logger = getLogger().logger
    console_logger = StreamHandler(sys.stdout)
    console_logger.setFormatter(TermFormatter(format))
    root_logger.addHandler(console_logger)
    root_logger.setLevel(log_level)


def getLogger(name='anvil'):
    return TermAdapter(logging.getLogger(name))
