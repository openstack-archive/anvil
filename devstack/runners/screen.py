# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import time
import re

from devstack import log as logging
from devstack import shell as sh
from devstack import utils

LOG = logging.getLogger("install.screen")

SCREEN_MAKE = ['screen', '-d', '-m', '-S', '%NAME%', '-t', '%NAME%']
LIST_CMD = ['screen', '-list']
KILL_CMD = ['screen', '-r', "%ENTRY%", '-X', 'kill']
QUIT_CMD = ['screen', '-r', "%ENTRY%", '-X', 'kill']
NAME_POSTFIX = ".devstack"
RUN_TYPE = "SCREEN"
TYPE = "TYPE"


class ScreenRunner(object):
    def __init__(self):
        pass

    def stop(self, name, *args, **kargs):
        real_name = name + NAME_POSTFIX
        (sysout, _) = sh.execute(*LIST_CMD)
        lines = sysout.splitlines()
        entries = list()
        lookfor = r"^(\d+\." + re.escape(real_name) + r")\s+(.*)$"
        for line in lines:
            cleaned_line = line.strip()
            if len(cleaned_line) == 0:
                continue
            mtch = re.match(lookfor, cleaned_line)
            if not mtch:
                continue
            kill_entry = mtch.group(1)
            entries.append(kill_entry)
        for entry in entries:
            params = dict()
            params['ENTRY'] = entry
            kill_cmd = [{'cmd':KILL_CMD}]
            utils.execute_template(*kill_cmd, params=params, **kargs)
            time.sleep(2)
            quit_cmd = [{'cmd':QUIT_CMD}]
            utils.execute_template(*kill_cmd, params=params, **kargs)

    def start(self, name, program, *args, **kargs):
        app_dir = kargs.get('app_dir')
        params = dict()
        params['NAME'] = name + NAME_POSTFIX
        runcmd = SCREEN_MAKE + [program] + list(args)
        cmds = [{'cmd':runcmd}]
        utils.execute_template(*cmds, params=params, cwd=app_dir, **kargs)
        return None
