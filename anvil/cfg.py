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


# Todo: inject all config merges into class below
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
    opt: "some-additional-data-$(source:option)-some-postfix-data", where:
        opt    - base option name
        source - other source config (i.e. other *.yaml file) from which we
                 should get 'option'
        option - option name in 'source'
    In other words it means that loader will try to find and read 'option' from
    'source'.

    Any source config also allows:
        References to itself via it's name (opt: "$(source:opt)",
        in file - source.yaml)

        References to auto parameters (opt: $(auto:ip), will insert current ip).
        'auto' allows next options: 'ip', 'hostname' and 'home'

        Implicit and multi references just like
        s.yaml => opt: "here 3 opts: $(source:opt), $(source2:opt) and $(auto:ip)".

    Exception cases:
      * if reference 'option' does not exist than YamlOptionException is raised
      * if config 'source' does not exist than YamlConfException is raised
      * if reference loop found than YamlLoopException is raised

    Config file example:
    (file sample.yaml)

    reference: "$(source:option)"
    ip: "$(auto:ip)"
    self_ref: "$(sample:ip)"  # this will equal ip option.
    opt: "http://$(auto:ip)/"
    """

    # Todo (vnovikov): may be it makes sense to add functionality for eval
    # operations (see example below)
    # file s1 => opt: 1
    # file s2 => opt: 2
    # file s3 => opt: 3
    # file s0 => opt: $(s1:opt) + $(s2:opt) * $(s3:opt)
    # Result for `s0 => opt` will equal 7

    def __init__(self, path):
        self._conf_ext = '.yaml'
        self._ref_pattern = re.compile(r"\$\(([\w\d-]+)\:([\w\d-]+)\)")
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

    def _process_string(self, conf, option, value):
        """Processing string (and reference links) values via regexp."""
        processed = value

        # search string value for references
        matches = re.findall(self._ref_pattern, value)

        if matches:
            # Checking reference stack and appending pair of the current
            # (config, option) to it.
            if (conf, option) in self._ref_stack:
                raise exceptions.YamlLoopException(conf, option, self._ref_stack)

            self._ref_stack.append((conf, option))

        # Process each reference in value (one by one)
        for ref_conf, ref_opt in matches:
            self._cache(ref_conf)

            if ref_opt not in self._cached[ref_conf]:
                raise exceptions.YamlOptionNotFoundException(
                    conf, option, ref_conf, ref_opt
                )

            val = self._process(ref_conf, ref_opt,
                                self._cached[ref_conf][ref_opt])

            # Note (vnovikov): do type conversion to make re.sub working and
            # backup-restore original type to restore it if needed (it's needed
            # to correct process non-string reference values).
            val_type = type(val)
            processed = re.sub(self._ref_pattern, str(val), processed, count=1)

            if val_type != str and processed == str(val):
                processed = val_type(processed)

        if matches:
            self._ref_stack.pop()

        self._cached[conf][option] = processed
        return processed

    def _process_dict(self, conf, option, value):
        """Process dictionary values."""
        processed = utils.OrderedDict()
        for opt, val in sorted(value.items()):
            res = self._process(conf, opt, val)
            processed[opt] = res
        return processed

    def _process_iterable(self, conf, option, value):
        """Process list, set or tuple values."""
        processed = []
        for item in value:
            processed.append(self._process(conf, option, item))
        return processed

    def _process_asis(self, value):
        """Process built-in values."""
        return value

    def _process(self, conf, option, value):
        """Base recursive method for processing references."""
        if isinstance(value, basestring):
            processed = self._process_string(conf, option, value)
        elif isinstance(value, dict):
            processed = self._process_dict(conf, option, value)
        elif isinstance(value, (list, set, tuple)):
            processed = self._process_iterable(conf, option, value)
        else:
            processed = self._process_asis(value)

        return processed

    def _cache(self, conf):
        """Cache config file into memory to avoid re-reading it from disk."""
        if conf not in self._cached:
            path = sh.joinpths(self._path, conf + self._conf_ext)
            if not sh.isfile(path):
                raise exceptions.YamlConfigNotFoundException(path)

            # Todo (vnovikov): may be it makes sense to reintroduce load_yaml
            # for returning OrderedDict with the same order as options placement
            # in source yaml file...
            self._cached[conf] = utils.load_yaml(path) or {}

    def _precache(self):
        """Cache and process predefined auto-references"""
        for conf, options in self._predefined_refs.items():

            if conf in self._processed:
                return

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
            self._cache(conf)
            self._processed[conf] = self._process(conf, None, self._cached[conf])

        return self._processed[conf]


def create_parser(cfg_cls, component, fns=None):
    templatize_values = component.get_bool_option('template_config')
    cfg_opts = {
        'fns': fns,
        'templatize_values': templatize_values,
    }
    return cfg_cls(**cfg_opts)
