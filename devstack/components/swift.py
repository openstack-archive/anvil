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

from devstack import component as comp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

LOG = logging.getLogger("devstack.components.swift")

#id
TYPE = settings.SWIFT


class SwiftUninstaller(object):
    def __init__(self, *args, **kargs):
        pass

    def unconfigure(self):
        raise NotImplementedError()

    def uninstall(self):
        raise NotImplementedError()


class SwiftInstaller(object):
    def __init__(self, *args, **kargs):
        pass

    def download(self):
        raise NotImplementedError()

    def configure(self):
        raise NotImplementedError()

    def pre_install(self):
        raise NotImplementedError()

    def install(self):
        raise NotImplementedError()

    def post_install(self):
        raise NotImplementedError()


class SwiftRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, TYPE, *args, **kargs)


def describe(opts=None):
    description = """
 Module: {module_name}
  Description:
   {description}
  Component options:
   {component_opts}
"""
    params = dict()
    params['component_opts'] = "TBD"
    params['module_name'] = __name__
    params['description'] = __doc__ or "Handles actions for the swift component."
    out = description.format(**params)
    return out.strip("\n")
