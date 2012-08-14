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

def _pformat(item, line_accum, indent, value_functor=None, key_functor=None):

    def identity_functor(v):
        return v

    if not value_functor:
        value_functor = identity_functor

    if not key_functor:
        key_functor = identity_functor

    if isinstance(item, (list, set, tuple)):
        indent_string = "-" * (indent)
        for i in item:
            if isinstance(i, (list, set, tuple, dict)):
                line_accum.append("|--%s+" % (indent_string))
                _pformat(i, line_accum, indent + 2, value_functor, key_functor)
            else:
                line_accum.append("|--%s %s" % (indent_string,
                                                value_functor(i)))
    elif isinstance(item, (dict)):
        indent_string = "-" * (indent)
        for (k, v) in item.items():
            if isinstance(v, (list, set, tuple, dict)):
                line_accum.append("|--%s+ %s =>" % (indent_string,
                                                    key_functor(k)))
                _pformat(v, line_accum, indent + 2, value_functor, key_functor)
            else:
                line_accum.append("|--%s %s => %s" % (indent_string,
                                                      key_functor(k),
                                                      value_functor(v)))
    else:
        indent_string = " " * (indent)
        line_accum.append("%s%s" % (indent_string,
                                    value_functor(item)))


def pformat(item, value_functor=None, key_functor=None):
    line_accum = []
    _pformat(item, line_accum, 0, value_functor, key_functor)
    return line_accum


def pprint(item, value_functor=None, key_functor=None):
    lines = pformat(item, value_functor, key_functor)
    print("\n".join(lines))
