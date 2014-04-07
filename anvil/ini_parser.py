# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2013 Yahoo! Inc. All Rights Reserved.
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

import ConfigParser
from ConfigParser import DEFAULTSECT
from ConfigParser import NoOptionError
from ConfigParser import NoSectionError
from StringIO import StringIO

import iniparse
from iniparse import ini

import re

from anvil import log as logging
from anvil import utils

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


class AnvilConfigParser(iniparse.RawConfigParser):
    """Extends RawConfigParser with the following functionality:
    1. All commented options with related comments belong to
    their own section, but not to the global scope. This is
    needed to insert new options into proper position after
    same commented option in the section, if present.
    2. Override set option behavior to insert option right
    after same commented option, if present, otherwise insert
    in the section beginning.
    3. Includes [DEFAULT] section if present (but not present in original).
    """

    # commented option regexp
    option_regex = re.compile(
        r"""
            ^[;#]   # comment line starts with ';' or '#'
            \s*     # then maybe some spaces
                    # then option name
            ([^:=\s[]   # at least one non-special symbol here
            [^:=]*?)    # option continuation
            \s*     # then maybe some spaces
            [:=]    # option-value separator ':' or '='
            .*      # then option value
            $       # then line ends
        """, re.VERBOSE)

    def __init__(self, defaults=None, dict_type=dict, include_defaults=True):
        super(AnvilConfigParser, self).__init__(defaults=defaults,
                                                dict_type=dict_type)
        self._include_defaults = include_defaults

    def readfp(self, fp, filename=None):
        super(AnvilConfigParser, self).readfp(fp, filename)
        self._on_after_file_read()

    def set(self, section, option, value):
        """Overrides option set behavior."""
        try:
            self._set_section_option(self.data[section], option, value)
        except KeyError:
            raise NoSectionError(section)

    def _sections(self):
        """Gets all the underlying sections (including DEFAULT). The underlying
        iniparse library seems to exclude the DEFAULT section which makes it
        hard to tell if we should include the DEFAULT section in output or
        whether the library will include it for us.
        """
        sections = set()
        for x in self.data._data.contents:
            if isinstance(x, ini.LineContainer):
                sections.add(x.name)
        return sections

    def write(self, fp):
        """Writes sections but also includes the default section if it is not
        present in the backing data but should be present in the output data.
        """
        if self.data._bom:
            fp.write(u'\ufeff')
        default_added = False
        if self._include_defaults and DEFAULTSECT not in self._sections():
            try:
                sect = self.data[DEFAULTSECT]
            except KeyError:
                pass
            else:
                default_added = True
                fp.write("%s\n" % (ini.SectionLine(DEFAULTSECT)))
                for lines in sect._lines:
                    fp.write("%s\n" % (lines))
        data = "%s" % (self.data._data)
        if default_added and data:
            # Remove extra spaces since we added a section before this.
            data = data.lstrip()
            data = "\n" + data
        fp.write(data)

    def _on_after_file_read(self):
        """This function is called after reading config file
        to move all commented lines into section they belong to,
        otherwise such commented lines are placed on top level,
        that is not very suitable for us.
        """
        curr_section = None
        pending_lines = []
        remove_lines = []
        for line_obj in self.data._data.contents:
            if isinstance(line_obj, ini.LineContainer):
                curr_section = line_obj
                pending_lines = []
            else:
                if curr_section is not None:
                    pending_lines.append(line_obj)
                    # if line is commented option - add it and all
                    # pending lines into current section
                    if self.option_regex.match(line_obj.line) is not None:
                        curr_section.extend(pending_lines)
                        remove_lines.extend(pending_lines)
                        pending_lines = []

        for line_obj in remove_lines:
            self.data._data.contents.remove(line_obj)

    @classmethod
    def _set_section_option(cls, section, key, value):
        """This function is used to override the __setitem__ behavior
        of the INISection to search suitable place to insert new
        option if it doesn't exist. The 'suitable' place is
        considered to be after same commented option, if present,
        otherwise new option is placed at the section beginning.
        """
        if section._optionxform:
            xkey = section._optionxform(key)
        else:
            xkey = key
        if xkey in section._compat_skip_empty_lines:
            section._compat_skip_empty_lines.remove(xkey)

        if xkey not in section._options:
            # create a dummy object - value may have multiple lines
            obj = ini.LineContainer(ini.OptionLine(key, ''))

            # search for the line index to insert after
            line_idx = 0
            section_lines = section._lines[-1].contents
            for idx, line_obj in reversed(list(enumerate(section_lines))):
                if not isinstance(line_obj, ini.LineContainer):
                    if line_obj.line is not None:
                        match_res = cls.option_regex.match(line_obj.line)
                        if match_res is not None and match_res.group(1) == xkey:
                            line_idx = idx
                            break

            # insert new parameter object on the next line after
            # commented option, otherwise insert it at the beginning
            section_lines.insert(line_idx + 1, obj)
            section._options[xkey] = obj
        section._options[xkey].value = value


class RewritableConfigParser(ConfigHelperMixin, AnvilConfigParser, StringiferMixin):
    def __init__(self, fns=None, templatize_values=False):
        ConfigHelperMixin.__init__(self, templatize_values)
        AnvilConfigParser.__init__(self)
        StringiferMixin.__init__(self)
        # Make option names case sensitive
        # See: http://docs.python.org/library/configparser.html#ConfigParser.RawConfigParser.optionxform
        self.optionxform = str
        if fns:
            for f in fns:
                self.read(f)


class DefaultConf(object):
    """This class represents the data/format of the config file with
    a large DEFAULT section.
    """

    current_section = DEFAULTSECT

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


def create_parser(cfg_cls, component, fns=None):
    templatize_values = component.get_bool_option('template_config')
    cfg_opts = {
        'fns': fns,
        'templatize_values': templatize_values,
    }
    return cfg_cls(**cfg_opts)
