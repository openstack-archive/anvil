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
import os
import sys

#requires http://pypi.python.org/pypi/termcolor
#but the colors make it worth it :-)
from termcolor import colored

# methods
getLogger = logging.getLogger


class TermFormatter(logging.Formatter):
    def __init__(self, reg_fmt, date_format):
        logging.Formatter.__init__(self, reg_fmt, date_format)

    def format(self, record):
        lvl = record.levelno
        lvlname = record.levelname
        if lvl == logging.DEBUG:
            lvlname = colored(lvlname, 'blue')
        elif lvl == logging.INFO:
            lvlname = colored(lvlname, 'cyan')
        elif lvl == logging.WARNING:
            lvlname = colored(lvlname, 'yellow')
        elif lvl == logging.ERROR:
            lvlname = colored(lvlname, 'red')
        elif lvl == logging.CRITICAL:
            lvlname = colored(lvlname, 'red')
            record.msg = colored(record.msg, attrs=['bold', 'blink'])
        record.levelname = lvlname
        return logging.Formatter.format(self, record)


class TermHandler(logging.Handler):
    STREAM = sys.stdout
    DO_FLUSH = True
    NL = os.linesep

    def __init__(self):
        logging.Handler.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        if msg is not None:
            TermHandler.STREAM.write(msg + TermHandler.NL)
            if TermHandler.DO_FLUSH:
                TermHandler.STREAM.flush()
