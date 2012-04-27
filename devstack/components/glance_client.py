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

from urlparse import urlunparse

from devstack import component as comp
from devstack import log as logging

LOG = logging.getLogger("devstack.components.glance_client")


class GlanceClientUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, *args, **kargs)


class GlanceClientInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, *args, **kargs)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "glanceclient_repo"),
            'branch': ("git", "glanceclient_branch"),
        })
        return places


class GlanceClientRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, *args, **kargs)


def get_shared_params(config):
    mp = dict()

    host_ip = config.get('host', 'ip')
    glance_host = config.getdefaulted('glance', 'glance_host', host_ip)
    mp['GLANCE_HOST'] = glance_host
    glance_port = config.getdefaulted('glance', 'glance_port', '9292')
    mp['GLANCE_PORT'] = glance_port
    glance_protocol = config.getdefaulted('glance', 'glance_protocol', 'http')
    mp['GLANCE_PROTOCOL'] = glance_protocol

    # Uri's of the http/https endpoints
    mp['GLANCE_HOSTPORT'] = urlunparse((glance_protocol,
                                         "%s:%s" % (glance_host, glance_port),
                                         "", "", "", ""))

    return mp
