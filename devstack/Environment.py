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
    env_copy = dict(os.environ)
    return env_copy


def get_environment_key(key, default_val=None):
    LOG.debug("Looking up environment variable %s" % (key))
    val = get_environment().get(key)
    if(val == None):
        LOG.debug("Could not find anything in environment variable %s (using default value %s)" % (key, default_val))
        val = default_val
    return val


def get_environment_bool(key, default_val=False):
    val = get_environment_key(key, None)
    if(val == None):
        return default_val
    return _str2bool(val)
