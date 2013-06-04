# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2013 Yahoo! Inc. All Rights Reserved.
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
from anvil.components.configurators import base

# Config files messed with...
HORIZON_LOCAL_SETTINGS_CONF = "local_settings.py"
HORIZON_APACHE_CONF = 'horizon_apache.conf'
CONFIGS = [HORIZON_LOCAL_SETTINGS_CONF, HORIZON_APACHE_CONF]

class HorizonConfigurator(base.Configurator):

    def __init__(self, installer):
        super(HorizonConfigurator, self).__init__(installer, CONFIGS)

    def target_config(self, config_name):
        if config_name == HORIZON_LOCAL_SETTINGS_CONF:
            return sh.joinpths(self.installer.get_option('app_dir'),
                               'openstack_dashboard',
                               'local',
                               config_name)
        else:
            return super(HorizonConfigurator, self).target_config(config_name)


class HorizonRhelConfigurator(HorizonConfigurator):

    def __init__(self, installer):
        super(HorizonRhelConfigurator, self).__init__(installer)
