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

import sys

import termcolor

from anvil import env
from anvil import type_utils as tu

COLORS = termcolor.COLORS.keys()

LOG_COLOR = True
if 'LOG_COLOR' in env.get():
    LOG_COLOR = tu.make_bool(env.get_key('LOG_COLOR'))
if not sys.stdout.isatty():
    LOG_COLOR = False


def color_enabled():
    return LOG_COLOR


def quote(data, quote_color='green', **kargs):
    if not color_enabled():
        return "'%s'" % (data)
    else:
        text = str(data)
        if len(text) == 0:
            text = "''"
        return color(text, quote_color, **kargs)


def color(data, color_to_be, bold=False, underline=False, blink=False):
    text = str(data)
    text_attrs = list()
    if bold:
        text_attrs.append('bold')
    if underline:
        text_attrs.append('underline')
    if blink:
        text_attrs.append('blink')
    if color_enabled() and color_to_be in COLORS:
        return termcolor.colored(text, color_to_be, attrs=text_attrs)
    else:
        return text
