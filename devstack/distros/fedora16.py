# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#    Copyright (C) 2012 New Dream Network, LLC (DreamHost) All Rights Reserved.
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

"""Platform-specific logic for RedHat Fedora 16 components.
"""

from devstack import log as logging

from devstack.distros import rhel6

LOG = logging.getLogger(__name__)

# See: http://wiki.libvirt.org/page/SSHPolicyKitSetup
# FIXME: take from distro config??
# TODO(mikeyp) check correct path for fedora
LIBVIRT_POLICY_FN = "/etc/polkit-1/localauthority/50-local.d/50-libvirt-access.pkla"


class DBInstaller(rhel6.DBInstaller):
    pass


class HorizonInstaller(rhel6.HorizonInstaller):
    pass


class NovaInstaller(rhel6.NovaInstaller):
    pass
