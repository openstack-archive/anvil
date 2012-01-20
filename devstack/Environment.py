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

import os

import Logger

TRUE_VALUES = ['yes', 'true', 't', '1', 'on']
LOG = Logger.getLogger("install.environment")


def _str2bool(value_str):
    if(value_str.lower().strip() in TRUE_VALUES):
        return True
    return False


def get_environment():
    return dict(os.environ)


def get_environment_key(key, default_value=None):
    LOG.debug("Looking up environment variable \"%s\"" % (key))
    value = get_environment().get(key)
    if(value == None):
        LOG.debug("Could not find anything in environment variable \"%s\"" % (key))
        value = default_value
    else:
        LOG.debug("Found \"%s\" in environment variable \"%s\"" % (value, key))
    return value


def get_environment_bool(key, default_value=False):
    value = get_environment_key(key, None)
    if(value == None):
        return default_value
    return _str2bool(value)
