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

import logging
from termcolor import colored

COLOR_MAP = {
    logging.DEBUG: 'blue',
    logging.INFO: 'cyan',
    logging.WARNING: 'yellow',
    logging.ERROR: 'red',
    logging.CRITICAL: 'red',
}

COLOR_ATTRS = {
    logging.CRITICAL: ['bold', 'blink'],
}


class TermFormatter(logging.Formatter):
    def __init__(self, reg_fmt=None, date_format=None):
        logging.Formatter.__init__(self, reg_fmt, date_format)

    def format(self, record):
        lvl = record.levelno
        color = COLOR_MAP.get(lvl)
        if color:
            record.levelname = colored(record.levelname, color)
        attrs = COLOR_ATTRS.get(lvl)
        if attrs:
            record.msg = colored(record.msg, attrs=attrs)
        return logging.Formatter.format(self, record)
