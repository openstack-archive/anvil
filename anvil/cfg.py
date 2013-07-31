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

# This one doesn't keep comments but does seem to work better
import ConfigParser
from ConfigParser import NoOptionError
from ConfigParser import NoSectionError

import re

from StringIO import StringIO

# This one keeps comments but has some weirdness with it
import iniparse

from anvil import log as logging
from anvil import shell as sh
from anvil import utils

INTERP_PAT = r"\s*\$\(([\w\d-]+):([\w\d-]+)\)\s*"

LOG = logging.getLogger(__name__)


class StringiferMixin(object):
    def __init__(self):
        pass

    def stringify(self, fn=None):
        outputstream = StringIO()
        self.write(outputstream)
        contents = utils.add_header(fn, outputstream.getvalue())
        return contents


class ConfigHelperMixin(object):
    DEF_INT = 0
    DEF_FLOAT = 0.0
    DEF_BOOLEAN = False
    DEF_BASE = None

    def __init__(self, templatize_values=False):
        self.templatize_values = templatize_values

    def get(self, section, option):
        value = self.DEF_BASE
        try:
            value = super(ConfigHelperMixin, self).get(section, option)
        except NoSectionError:
            pass
        except NoOptionError:
            pass
        return value

    def _template_value(self, option, value):
        if not self.templatize_values:
            return value
        tpl_value = StringIO()
        safe_value = str(option)
        for c in ['-', ' ', '\t', ':', '$', '%', '(', ')']:
            safe_value = safe_value.replace(c, '_')
        tpl_value.write("$(%s)" % (safe_value.upper().strip()))
        comment_value = str(value).strip().encode('string_escape')
        for c in ['(', ')', '$']:
            comment_value = comment_value.replace(c, '')
        comment_value = comment_value.strip()
        tpl_value.write(" # %s" % (comment_value))
        return tpl_value.getvalue()

    def set(self, section, option, value):
        if not self.has_section(section) and section.lower() != 'default':
            self.add_section(section)
        value = self._template_value(option, value)
        super(ConfigHelperMixin, self).set(section, option, value)

    def remove_option(self, section, option):
        if self.has_option(section, option):
            super(ConfigHelperMixin, self).remove_option(section, option)

    def getboolean(self, section, option):
        if not self.has_option(section, option):
            return self.DEF_BOOLEAN
        return super(ConfigHelperMixin, self).getboolean(section, option)

    def getfloat(self, section, option):
        if not self.has_option(section, option):
            return self.DEF_FLOAT
        return super(ConfigHelperMixin, self).getfloat(section, option)

    def getint(self, section, option):
        if not self.has_option(section, option):
            return self.DEF_INT
        return super(ConfigHelperMixin, self).getint(section, option)

    def getlist(self, section, option):
        return self.get(section, option).split(",")


class BuiltinConfigParser(ConfigHelperMixin, ConfigParser.RawConfigParser, StringiferMixin):
    def __init__(self, fns=None, templatize_values=False):
        ConfigHelperMixin.__init__(self, templatize_values)
        ConfigParser.RawConfigParser.__init__(self)
        StringiferMixin.__init__(self)
        # Make option names case sensitive
        # See: http://docs.python.org/library/configparser.html#ConfigParser.RawConfigParser.optionxform
        self.optionxform = str
        if fns:
            for f in fns:
                self.read(f)


class RewritableConfigParser(ConfigHelperMixin, iniparse.RawConfigParser, StringiferMixin):
    def __init__(self, fns=None, templatize_values=False):
        ConfigHelperMixin.__init__(self, templatize_values)
        iniparse.RawConfigParser.__init__(self)
        StringiferMixin.__init__(self)
        # Make option names case sensitive
        # See: http://docs.python.org/library/configparser.html#ConfigParser.RawConfigParser.optionxform
        self.optionxform = str
        if fns:
            for f in fns:
                self.read(f)


class DefaultConf(object):
    """This class represents the data/format of the config file with
    a large DEFAULT section"""

    current_section = "DEFAULT"

    def __init__(self, backing, current_section=None):
        self.backing = backing
        self.current_section = current_section or self.current_section

    def add_with_section(self, section, key, value, *values):
        real_key = str(key)
        real_value = ""
        if len(values):
            str_values = [str(value)] + [str(v) for v in values]
            real_value = ",".join(str_values)
        else:
            real_value = str(value)
        LOG.debug("Added conf key %r with value %r under section %r",
                  real_key, real_value, section)
        self.backing.set(section, real_key, real_value)

    def add(self, key, value, *values):
        self.add_with_section(self.current_section, key, value, *values)

    def remove(self, section, key):
        self.backing.remove_option(section, key)


class YamlInterpolator(object):
    def __init__(self, base):
        self.included = {}
        self.interpolated = {}
        self.base = base
        self.auto_specials = {
            'ip': utils.get_host_ip,
            'home': sh.gethomedir,
            'hostname': sh.hostname,
        }

    def _interpolate_iterable(self, what):
        if isinstance(what, (set)):
            n_what = set()
            for v in what:
                n_what.add(self._interpolate(v))
            return n_what
        else:
            n_what = []
            for v in what:
                n_what.append(self._interpolate(v))
            if isinstance(what, (tuple)):
                n_what = tuple(n_what)
            return n_what

    def _interpolate_dictionary(self, what):
        n_what = {}
        for (k, v) in what.iteritems():
            n_what[k] = self._interpolate(v)
        return n_what

    def _include_dictionary(self, what):
        n_what = {}
        for (k, value) in what.iteritems():
            n_what[k] = self._do_include(value)
        return n_what

    def _include_iterable(self, what):
        if isinstance(what, (set)):
            n_what = set()
            for v in what:
                n_what.add(self._do_include(v))
            return n_what
        else:
            n_what = []
            for v in what:
                n_what.append(self._do_include(v))
            if isinstance(what, (tuple)):
                n_what = tuple(n_what)
            return n_what

    def _interpolate(self, value):
        new_value = value
        if value and isinstance(value, (basestring, str)):
            new_value = self._interpolate_string(value)
        elif isinstance(value, (dict)):
            new_value = self._interpolate_dictionary(value)
        elif isinstance(value, (list, set, tuple)):
            new_value = self._interpolate_iterable(value)
        return new_value

    def _interpolate_string(self, what):
        if not re.search(INTERP_PAT, what):
            # Leave it alone if the sub won't do
            # anything to begin with
            return what

        def replacer(match):
            who = match.group(1).strip()
            key = match.group(2).strip()
            (is_special, special_value) = self._process_special(who, key)
            if is_special:
                return special_value
            if who not in self.interpolated:
                self.interpolated[who] = self.included[who]
                self.interpolated[who] = self._interpolate(self.included[who])
            return str(self.interpolated[who][key])

        return re.sub(INTERP_PAT, replacer, what)

    def _process_special(self, who, key):
        if who and who.lower() in ['auto']:
            if key not in self.auto_specials:
                raise KeyError("Unknown auto key %r" % (key))
            functor = self.auto_specials[key]
            return (True, functor())
        return (False, None)

    def _include_string(self, what):
        if not re.search(INTERP_PAT, what):
            # Leave it alone if the sub won't do
            # anything to begin with
            return what

        def replacer(match):
            who = match.group(1).strip()
            key = match.group(2).strip()
            (is_special, special_value) = self._process_special(who, key)
            if is_special:
                return special_value
            # Process there includes and then
            # fetch the value that should have been
            # populated
            self._process_includes(who)
            return str(self.included[who][key])

        return re.sub(INTERP_PAT, replacer, what)

    def _do_include(self, value):
        new_value = value
        if value and isinstance(value, (basestring, str)):
            new_value = self._include_string(value)
        elif isinstance(value, (dict)):
            new_value = self._include_dictionary(value)
        elif isinstance(value, (list, set, tuple)):
            new_value = self._include_iterable(value)
        return new_value

    def _process_includes(self, root):
        if root in self.included:
            return
        pth = sh.joinpths(self.base, "%s.yaml" % (root))
        if not sh.isfile(pth):
            self.included[root] = {}
            return
        self.included[root] = utils.load_yaml(pth)
        self.included[root] = self._do_include(self.included[root])

    def extract(self, root):
        if root in self.interpolated:
            return self.interpolated[root]
        self._process_includes(root)
        self.interpolated[root] = self.included[root]
        self.interpolated[root] = self._interpolate(self.interpolated[root])
        return self.interpolated[root]


def create_parser(cfg_cls, component, fns=None):
    templatize_values = component.get_bool_option('template_config')
    cfg_opts = {
        'fns': fns,
        'templatize_values': templatize_values,
    }
    return cfg_cls(**cfg_opts)
