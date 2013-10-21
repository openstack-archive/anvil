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
from anvil import settings
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


class YamlMergeLoader(object):
    """Holds merging process component options (based on Yaml reference loader).
    """

    def __init__(self, root_dir):
        self._root_dir = root_dir
        self._base_loader = YamlRefLoader(settings.COMPONENT_CONF_DIR)

    def _get_dir_opts(self, component):
        component_dir = sh.joinpths(self._root_dir, component)
        trace_dir = sh.joinpths(component_dir, 'traces')
        app_dir = sh.joinpths(component_dir, 'app')
        return {
            'app_dir': app_dir,
            'component_dir': component_dir,
            'root_dir': self._root_dir,
            'trace_dir': trace_dir,
        }

    def _apply_persona(self, component, persona):
        """Apply persona specific and global options according to component.

        Include the general.yaml in each applying since it typically contains
        useful shared settings.
        """

        for conf in ('general', component):
            if persona is not None:
                persona_specific = persona.component_options.get(component, {})
                persona_global = persona.component_options.get('global', {})

                self._base_loader.update_cache(conf, persona_specific)
                self._base_loader.update_cache(conf, persona_global)

    def load(self, distro, component, persona=None):
        # NOTE (vnovikov): applying takes place before loading reference links
        self._apply_persona(component, persona)

        dir_opts = self._get_dir_opts(component)
        distro_opts = distro.options
        general_component_opts = self._base_loader.load('general')
        component_specific_opts = self._base_loader.load(component)

        # NOTE (vnovikov): merge order is the same as arguments order below.
        merged_opts = utils.merge_dicts(
            dir_opts,
            distro_opts,
            general_component_opts,
            component_specific_opts,
        )

        return merged_opts


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

    def _process_string(self, value):
        """Processing string (and reference links) values via regexp."""
        processed = value

        # Process each reference in value (one by one)
        for match in self._ref_pattern.finditer(value):
            ref_conf, ref_opt = match.groups()
            val = self._load_option(ref_conf, ref_opt)

            if match.group(0) == value:
                return val
            else:
                processed = re.sub(self._ref_pattern, str(val), processed, count=1)
        return processed

    def _process_dict(self, value):
        """Process dictionary values."""
        processed = utils.OrderedDict()
        for opt, val in sorted(value.items()):
            res = self._process(val)
            processed[opt] = res

        return processed

    def _process_iterable(self, value):
        """Process list, set or tuple values."""
        processed = []
        for item in value:
            processed.append(self._process(item))

        return processed

    def _process_asis(self, value):
        """Process built-in values."""
        return value

    def _process(self, value):
        """Base recursive method for processing references."""
        if isinstance(value, basestring):
            processed = self._process_string(value)
        elif isinstance(value, dict):
            processed = self._process_dict(value)
        elif isinstance(value, (list, set, tuple)):
            processed = self._process_iterable(value)
        else:
            processed = self._process_asis(value)

        return processed

    def _precache(self):
        """Cache and process predefined auto-references"""
        for conf, options in self._predefined_refs.items():
            if conf not in self._processed:
                processed = dict((option, functor())
                                 for option, functor in options.items())
                self._cached[conf] = processed
                self._processed[conf] = processed

    def _load_option(self, conf, opt):
        try:
            return self._processed[conf][opt]
        except KeyError:
            if (conf, opt) in self._ref_stack:
                raise exceptions.YamlLoopException(conf, opt, self._ref_stack)
            self._ref_stack.append((conf, opt))

            self._cache(conf)
            try:
                raw_value = self._cached[conf][opt]
            except KeyError:
                try:
                    cur_conf, cur_opt = self._ref_stack[-1]
                except IndexError:
                    cur_conf, cur_opt = None, None
                raise exceptions.YamlOptionNotFoundException(
                    cur_conf, cur_opt, conf, opt
                )
            result = self._process(raw_value)
            self._processed.setdefault(conf, {})[opt] = result

            self._ref_stack.pop()
            return result

    def _cache(self, conf):
        """Cache config file into memory to avoid re-reading it from disk."""
        if conf not in self._cached:
            path = sh.joinpths(self._path, conf + self._conf_ext)
            if not sh.isfile(path):
                raise exceptions.YamlConfigNotFoundException(path)

            self._cached[conf] = utils.load_yaml(path) or {}

    def update_cache(self, conf, dict2update):
        self._cache(conf)
        #for k, v in dict2update.items():
        #    self._cached[conf][k] = v

        # NOTE (vnovikov): should remove obsolete processed data
        self._cached[conf].update(dict2update)
        self._processed[conf] = {}

    def load(self, conf):
        """Load config `conf` from same yaml file with and resolve all
        references.
        """
        self._precache()
        self._cache(conf)
        # NOTE(imelnikov): some confs may be partially processed, so
        # we have to ensure all the options got loaded.
        for opt in self._cached[conf].iterkeys():
            self._load_option(conf, opt)
        # TODO(imelnikov: can we really restore original order here?
        self._processed[conf] = utils.OrderedDict(
            sorted(self._processed.get(conf, {}).iteritems())
        )
        return self._processed[conf]


def create_parser(cfg_cls, component, fns=None):
    templatize_values = component.get_bool_option('template_config')
    cfg_opts = {
        'fns': fns,
        'templatize_values': templatize_values,
    }
    return cfg_cls(**cfg_opts)
