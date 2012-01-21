# vim: tabstop=4 shiftwidth=4 softtabstop=4
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

from devstack import component as comp
from devstack import constants
from devstack import log as logging
from devstack import shell as sh
from devstack import utils

LOG = logging.getLogger("devstack.components.nova_conf")


class NovaConf():
    def __init__(self):
        self.lines = list()

    def add_list(self, key, *params):
        self.lines.append({'key': key, 'options': params})
        LOG.debug("Added nova conf key %s with values [%s]" % (key, ",".join(params)))

    def add_simple(self, key):
        self.lines.append({'key': key, 'options': None})
        LOG.debug("Added nova conf key %s" % (key))

    def add(self, key, value):
        self.lines.append({'key': key, 'options': [value]})
        LOG.debug("Added nova conf key %s with value [%s]" % (key, value))

    def _form_key(self, key, has_opts):
        key_str = "--" + str(key)
        if(has_opts):
            key_str += "="
        return key_str

    def generate(self, param_dict=None):
        gen_lines = list()
        for line_entry in self.lines:
            key = line_entry.get('key')
            opts = line_entry.get('options')
            if(not key or len(key) == 0):
                continue
            if(opts == None):
                key_str = self._form_key(key, False)
                full_line = key_str
            else:
                key_str = self._form_key(key, len(opts))
                filled_opts = list()
                for opt in opts:
                    filled_opts.append(utils.param_replace(str(opt), param_dict))
                full_line = key_str + ",".join(filled_opts)
            gen_lines.append(full_line)
        return utils.joinlinesep(*gen_lines)
