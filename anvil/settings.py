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

import os
import sys

from anvil import constants

# RC files generated / used
RC_FN_TEMPL = "%s.rc"

# Where the configs and templates should be at...
BIN_DIR = os.path.abspath(os.path.dirname(sys.argv[0]))
CONFIG_DIR = os.path.join(BIN_DIR, "conf")
DISTRO_DIR = os.path.join(CONFIG_DIR, "distros")
TEMPLATE_DIR = os.path.join(CONFIG_DIR, "templates")
PERSONA_DIR = os.path.join(CONFIG_DIR, "personas")
CONFIG_NAME = constants.CONFIG_NAME
CONFIG_LOCATION = os.path.join(CONFIG_DIR, CONFIG_NAME)


def gen_rc_filename(root_name):
    return RC_FN_TEMPL % (root_name)
