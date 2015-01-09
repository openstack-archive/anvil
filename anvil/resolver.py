# -*- coding: utf-8 -*-

# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2015 Yahoo! Inc. All Rights Reserved.
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

import platform
import re

from anvil import distro as distros
from anvil import origins
from anvil import persona as personas
from anvil import settings
from anvil import shell as sh
from anvil import utils


class Resolver(object):
    @staticmethod
    def _list_yamls(self, dirname):
        yamls = []
        for path in sh.listdir(dirname, files_only=True):
            if not path.endswith(".yaml"):
                continue
            path = sh.basename(path)
            yamls.append(path[0:-5])
        return yamls

    def _inject_percularities(self, distro, origins, persona):
        pass

    def resolve(self, distro, persona, origin):
        distro_filename = sh.joinpths(settings.DISTRO_DIR, "%s.yaml" % distro)
        if not sh.isfile(distro_filename):
            raise ValueError("Unknown distro named %s, valid distro names are %s"
                             % (distro, self._list_yamls(settings.DISTRO_DIR)))
        persona_filename = sh.joinpths(settings.PERSONA_DIR, "%s.yaml" % persona)
        if not sh.isfile(persona_filename):
            raise ValueError("Unknown persona named %s, valid persona names are %s"
                             % (persona, self._list_yamls(settings.PERSONA_DIR)))
        origin_filename = sh.joinpths(settings.ORIGINS_DIR, "%s.yaml" % persona)
        if not sh.isfile(origin_filename):
            raise ValueError("Unknown origin named %s, valid origin names are %s"
                             % (origin, self._list_yamls(settings.ORIGINS_DIR)))
        distro = distros.load(distro_filename)
        origins = origins.load(origin_filename)
        persona = personas.load(persona_filename)
        self._inject_percularities(origins, persona)
        persona.match([self.distro], origins)
        return (distro, origins, persona)
