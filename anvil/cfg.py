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

from anvil import exceptions
from anvil import log as logging
from anvil import shell as sh
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


# TODO(vnovikov): inject all config merges into class below
#class YamlMergeLoader(object):
#
#    def __init__(self, path):
#        self._merge_order = ('general',)
#        self._base_loader = YamlRefLoader(path)
#
#    def load(self, distro, component, persona, cli):
#
#        distro_opts = distro.options
#        general_component_opts = self._base_loader.load('general')
#        component_specific_opts = self._base_loader.load(component)
#        persona_component_opts = persona.component_options.get(component, {})
#        persona_global_opts = persona.component_options.get('global', {})
#        cli_opts = cli
#
#        merged_opts = utils.merge_dicts(
#            distro_opts,
#            general_component_opts,
#            component_specific_opts,
#            persona_component_opts,
#            persona_global_opts,
#            cli_opts,
#        )
#
#        return merged_opts


class YamlRefLoader(object):
    """Reference loader for *.yaml configs.

    Holds usual safe loading of the *.yaml files, caching, resolving and getting
    all reference links and transforming all data to python built-in types.

    Let's describe some basics.
    In this context reference means value which formatted just like:
    opt: "$(source:option)" , or
    opt: "prefix + $(source:option) + suffix", or
    opt: "$(source:list-option):1", or
    opt: "$(source:dict-option:dict-key):",
    where:
        opt    - base option name
        source - other source config (i.e. other *.yaml file) from which we
                 should get 'option'
        option - option name in 'source', key in the dictionary, list index, etc.

    In other words it means that loader will try to find and read 'option' from
    'source', or read value with index `1` in `list-option`, etc.

    Any source config also allows:
        References to itself via it's name (opt: "$(source:opt)",
        in file - source.yaml)

        References to auto parameters 'ip', 'hostname' and 'home':
        opt: $(auto:ip) # (will insert current ip).

        Implicit and multi references:
        s.yaml => opt: "here 3 opts: $(source:opt), $(source2:opt) and $(auto:ip)".

        References for list-like options to values by it's index:
        s.yaml => opt: "$(source:list-opt:1)".

        References for dictionary-like options to values via dict key:
        s.yaml => opt: "$(source:dict-opt:key-in-dict)".

        Complex and mutable references:
        s.yaml => opt: "suffix + $(source:dict-opt1:dict-opt2:list-opt:1)".

    Exception cases:
      * if reference 'option' does not exist than YamlOptionNotFoundException
        is raised
      * if config 'source' does not exist than YamlConfigNotFoundException is
        raised
      * if reference loop found than YamlLoopException is raised
    """

    def __init__(self, path):
        self._conf_ext = '.yaml'
        self._ref_pattern = re.compile(r"\$\((([\w\d-]+\:)+[\w\d-]+)\)")
        self._predefined_refs = {
            'auto': {
                'ip': utils.get_host_ip,
                'home': sh.gethomedir,
                'hostname': sh.hostname,
            }
        }
        self._path = path     # path to root directory with configs
        self._cached = {}     # buffer to save already loaded configs
        self._processed = {}  # buffer to save already processed configs
        self._ref_stack = []  # stack for controlling reference loop

    def _search4references(self, value):
        """Search string value for references, parse its and split to chunks.
        Try all values to convert its for list indexes, or dict keys.
        """
        matches = re.findall(self._ref_pattern, value)
        matches = map(lambda match: match[0].split(':'),
                      matches)

        for mi, match in enumerate(matches):
            for ci, chunk in enumerate(match):
                try:
                    match[ci] = int(chunk)
                except ValueError:
                    pass
            matches[mi] = tuple(match)

        return matches

    def _get_cached_value(self, path2value):
        """Return already read value from cache."""
        return reduce(
            lambda x, y: x.__getitem__(y),
            (self._cached,) + path2value
        )

    def _set_cached_value(self, path2value, value):
        # NOTE (vnovikov): set old cached value to new processed one,
        # please select the most understandable from below:)

        #cached = self._cached
        #for sub_path in path:
        #    cached = cached[sub_path]
        #cached[opt] = value

        path, last_opt = path2value[:-1], path2value[-1]
        cached = reduce(lambda x, y: x.__getitem__(y), (self._cached,) + path)
        cached[last_opt] = value

    def _process_string(self, path2value, value):
        """Processing string (and reference links) values via regexp."""
        processed = value
        matches = self._search4references(value)

        if matches:
            # Checking reference stack and appending pair of the current
            # (config, option) to it.
            if path2value in self._ref_stack:
                raise exceptions.YamlLoopException(path2value, self._ref_stack)

            self._ref_stack.append(path2value)

        # Process each reference in value (one by one).
        for path2reference in matches:
            self._cache(path2reference)
            try:
                not_processed = self._get_cached_value(path2reference)
            except (KeyError, IndexError):
                raise exceptions.YamlOptionNotFoundException(path2value,
                                                             path2reference)

            val = self._process(path2reference, not_processed)

            # NOTE (vnovikov): do checking lengths and str() to make re.sub
            # working to correct process non-string reference values and complex
            # references.
            processed = re.sub(self._ref_pattern, str(val), processed, count=1)
            if len(processed) == len(str(val)):
                processed = val

        if matches:
            self._ref_stack.remove(path2value)
            self._set_cached_value(path2value, processed)

        return processed

    def _process_dict(self, path2value, value):
        """Process dictionary values."""
        processed = utils.OrderedDict()
        for opt, val in sorted(value.items()):
            processed[opt] = self._process(path2value + (opt,), val)

        return processed

    def _process_iterable(self, path2value, value):
        """Process list, set or tuple values."""
        processed = []
        for index, val in enumerate(value):
            processed.append(self._process(path2value + (index,), val))

        return processed

    def _process_asis(self, value):
        """Process built-in values."""
        return value

    def _process(self, path2value, value):
        """Base recursive method for processing references."""
        if isinstance(value, basestring):
            processed = self._process_string(path2value, value)
        elif isinstance(value, dict):
            processed = self._process_dict(path2value, value)
        elif isinstance(value, (list, set, tuple)):
            processed = self._process_iterable(path2value, value)
        else:
            processed = self._process_asis(value)

        return processed

    def _cache(self, path2value):
        """Cache config file into memory to avoid re-reading it from disk."""
        conf = path2value[0]

        if conf not in self._cached:
            path = sh.joinpths(self._path, conf + self._conf_ext)
            if not sh.isfile(path):
                raise exceptions.YamlConfigNotFoundException(path)

            # TODO(vnovikov): may be it makes sense to reintroduce load_yaml
            # for returning OrderedDict with the same order as options placement
            # in source yaml file...
            self._cached[conf] = utils.load_yaml(path) or {}

    def _precache(self):
        """Cache and process predefined auto-references"""
        for conf, options in self._predefined_refs.items():

            if conf in self._processed:
                continue

            self._cached[conf] = {}
            for option, functor in options.items():
                self._cached[conf][option] = functor()

            self._processed[conf] = self._cached[conf]

    def load(self, conf):
        """Load config `conf` from same yaml file with and resolve all
        references.
        """
        self._precache()

        if conf not in self._processed:
            self._cache((conf,))
            self._processed[conf] = self._process((conf,), self._cached[conf])

        return self._processed[conf]


def create_parser(cfg_cls, component, fns=None):
    templatize_values = component.get_bool_option('template_config')
    cfg_opts = {
        'fns': fns,
        'templatize_values': templatize_values,
    }
    return cfg_cls(**cfg_opts)
