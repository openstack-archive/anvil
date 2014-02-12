# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2014 Yahoo! Inc. All Rights Reserved.
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

from anvil import shell as sh

from anvil.components import base_install as base


class GlobalRequirements(base.PythonComponent):
    def __init__(self, *args, **kargs):
        super(GlobalRequirements, self).__init__(*args, **kargs)
        app_dir = self.get_option('app_dir')
        self.requires_files = [
            sh.joinpths(app_dir, 'global-requirements.txt'),
        ]
