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


from anvil import log as logging
from anvil import packager as pack
from anvil import utils

import pip
from pip.util import get_installed_distributions

LOG = logging.getLogger(__name__)


def make_registry():
    installations = {}
    for dist in get_installed_distributions(local_only=True):
        freq = pip.FrozenRequirement.from_dist(dist, [])
        if freq.req and freq.name:
            name = freq.name.lower()
            installations[name] = freq.req
    # TODO(harlowja) use the pip version/requirement to enhance this...
    reg = pack.Registry()
    for (name, _req) in installations.items():
        reg.installed[name] = pack.NullVersion(name)
    LOG.debug("Identified %s packages already installed by pip", len(reg.installed))
    utils.log_object(reg.installed, logger=LOG, level=logging.DEBUG)
    return reg
