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

from anvil import env

import random as rand
import re
import sys

import termcolor


COLORS = termcolor.COLORS.keys()


def color_enabled():
    if str(env.get_key('LOG_COLOR')).strip().lower() in ['false', 'no', '0', 'off']:
        return False
    if not sys.stdout.isatty():
        return False
    return True


def random_color(data):
    if not color_enabled():
        return data
    new_data = list()
    for d in data:
        c = color(d, color=rand.choice(COLORS))
        new_data.append(c)
    return ''.join(new_data)


def quote(data, quote_color='green', **kargs):
    if not color_enabled():
        return "'%s'" % (data)
    else:
        text = str(data)
        if len(text) == 0:
            text = "''"
        return color(text, quote_color, **kargs)


def format(data, params):
    text = str(data)

    def replacer(match):
        param_name = match.group(1)
        return color(params[param_name], color=match.group(2).strip())

    return re.sub(r"\{([\w\d]+):(.*)\}", replacer, text)


def color(data, color, bold=False, underline=False, blink=False):
    text = str(data)
    text_attrs = list()
    if bold:
        text_attrs.append('bold')
    if underline:
        text_attrs.append('underline')
    if blink:
        text_attrs.append('blink')
    if color_enabled() and color in COLORS:
        return termcolor.colored(text, color, attrs=text_attrs)
    else:
        return text
