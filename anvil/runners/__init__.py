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

import abc
import weakref

from anvil.components import STATUS_UNKNOWN


class Runner(object):
    __meta__ = abc.ABCMeta

    def __init__(self, runtime):
        self.runtime = weakref.proxy(runtime)

    def start(self, app_name, app_pth, app_dir, opts):
        # Returns a file name that contains what was started
        pass

    def stop(self, app_name):
        # Stops the given app
        pass

    def status(self, app_name):
        # Attempt to give the status of a app + details
        return (STATUS_UNKNOWN, '')
