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


def center_text(text, fill, max_len):
    return '{0:{fill}{align}{size}}'.format(text, fill=fill, align="^", size=max_len)


def _pformat_list(lst, item_max_len):
    lines = []
    if not lst:
        lines.append("+------+")
        lines.append("'------'")
        return "\n".join(lines)
    entries = []
    max_len = 0
    for i in lst:
        e = pformat(i, item_max_len)
        for v in e.split("\n"):
            max_len = max(max_len, len(v) + 2)
        entries.append(e)
    lines.append("+%s+" % ("-" * (max_len)))
    for e in entries:
        for line in e.split("\n"):
            lines.append("|%s|" % (center_text(line, ' ', max_len)))
    lines.append("'%s'" % ("-" * (max_len)))
    return "\n".join(lines)


def _pformat_hash(hsh, item_max_len):
    lines = []
    if not hsh:
        lines.append("+-----+-----+")
        lines.append("'-----+-----'")
        return "\n".join(lines)
    # Figure out the lengths to place items in...
    max_key_len = 0
    max_value_len = 0
    entries = []
    for (k, v) in hsh.items():
        entry = ("%s" % (_pformat_escape(k, item_max_len)), "%s" % (pformat(v, item_max_len)))
        max_key_len = max(max_key_len, len(entry[0]) + 2)
        for v in entry[1].split("\n"):
            max_value_len = max(max_value_len, len(v) + 2)
        entries.append(entry)
    # Now actually do the placement since we have the lengths
    lines.append("+%s+%s+" % ("-" * max_key_len, "-" * max_value_len))
    for (key, value) in entries:
        value_lines = value.split("\n")
        lines.append("|%s|%s|" % (center_text(key, ' ', max_key_len),
                                  center_text(value_lines[0], ' ', max_value_len)))
        if len(value_lines) > 1:
            for j in range(1, len(value_lines)):
                lines.append("|%s|%s|" % (center_text("-", ' ', max_key_len),
                                          center_text(value_lines[j], ' ', max_value_len)))
    lines.append("'%s+%s'" % ("-" * max_key_len, "-" * max_value_len))
    return "\n".join(lines)


def _pformat_escape(item, item_max_len):
    item = _pformat_simple(item, item_max_len)
    item = item.replace("\n", "\\n")
    item = item.replace("\t", "\\t")
    return item


def _pformat_simple(item, item_max_len):
    if item_max_len is None or item_max_len < 0:
        return "%s" % (item)
    if item_max_len == 0:
        return ''
    item_str = "%s" % (item)
    if len(item_str) > item_max_len:
        # TODO(harlowja) use utf8 ellipse or '...'??
        item_str = item_str[0:item_max_len] + '...'
    return item_str


def pformat(item, item_max_len=None):
    if isinstance(item, (list, set, tuple)):
        return _pformat_list(item, item_max_len)
    elif isinstance(item, (dict)):
        return _pformat_hash(item, item_max_len)
    else:
        return _pformat_simple(item, item_max_len)


def pprint(item, item_max_len=None):
    print("%s" % (pformat(item, item_max_len)))
