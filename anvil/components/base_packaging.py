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

from anvil import component
from anvil import importer
from anvil import log as logging

LOG = logging.getLogger(__name__)

# Cache of accessed packagers
_PACKAGERS = {}


def make_packager(package, default_class, **kwargs):
    packager_name = package.get('packager_name') or ''
    packager_name = packager_name.strip()
    if packager_name:
        packager_cls = importer.import_entry_point(packager_name)
    else:
        packager_cls = default_class
    if packager_cls in _PACKAGERS:
        return _PACKAGERS[packager_cls]
    p = packager_cls(**kwargs)
    _PACKAGERS[packager_cls] = p
    return p


# Remove any private keys from a package dictionary
def filter_package(pkg):
    n_pkg = {}
    for (k, v) in pkg.items():
        if not k or k.startswith("_"):
            continue
        else:
            n_pkg[k] = v
    return n_pkg

class EmptyPackagingComponent(component.Component):
    def package(self):
        return None
