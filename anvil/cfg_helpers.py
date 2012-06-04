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

from anvil import constants
from anvil import log as logging
from anvil import settings
from anvil import shell as sh

PW_SECTION = 'passwords'
LOG = logging.getLogger(__name__)


def pprint(cfg_cache, group_by, order_by):

    if not cfg_cache:
        return

    LOG.debug("Grouping by %s", group_by.keys())
    LOG.debug("Ordering by %s", order_by)

    def item_format(key, value):
        return "\t%s=%s" % (str(key), str(value))

    def map_print(mp):
        for key in sorted(mp.keys()):
            value = mp.get(key)
            LOG.info(item_format(key, value))

    # First partition into our groups
    partitions = dict()
    for name in group_by.keys():
        partitions[name] = dict()

    # Now put the config cached values into there partitions
    for (k, v) in cfg_cache.items():
        for name in order_by:
            entries = partitions[name]
            if k.startswith(name):
                entries[k] = v
                break

    # Now print them..
    for name in order_by:
        nice_name = group_by.get(name, "???")
        if not nice_name.endswith(":"):
            nice_name = nice_name + ":"
        entries = partitions.get(name)
        if entries:
            LOG.info(nice_name)
            if entries:
                map_print(entries)


def make_id(section, option):
    joinwhat = []
    if section is not None:
        joinwhat.append(str(section))
    if option is not None:
        joinwhat.append(str(option))
    return "/".join(joinwhat)


def get_config_locations(start_locations=None):
    locs = []
    if start_locations:
        locs.extend(start_locations)
    locs.append(settings.CONFIG_LOCATION)
    locs.append(sh.joinpths("/etc", constants.PROG_NAME, settings.CONFIG_NAME))
    return locs


def find_config(locations=None):
    """
    Finds the potential anvil configuration files.
    """
    if not locations:
        locations = get_config_locations()
    real_paths = []
    for path in locations:
        LOG.debug("Looking for configuration in: %r", path)
        if sh.isfile(path):
            LOG.debug("Found configuration in: %r", path)
            real_paths.append(path)
    return real_paths
