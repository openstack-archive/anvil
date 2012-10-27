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

from anvil import log as logging
from anvil import shell as sh
from anvil import utils


LOG = logging.getLogger(__name__)

# TODO(harlowja): use git patching vs. raw patching??
PATCH_CMD = ['patch', '-p1']


def apply_patches(patch_files, working_dir):
    if not patch_files:
        return
    apply_files = []
    for p in patch_files:
        p = sh.abspth(p)
        if not sh.isfile(p):
            LOG.warn("Can not apply non-file patch %s", p)
        apply_files.append(p)
    if not apply_files:
        return
    if not sh.isdir(working_dir):
        LOG.warn("Can only apply %s patches 'inside' a directory and not '%s'",
                 len(apply_files), working_dir)
        return
    with utils.chdir(working_dir):
        for p in apply_files:
            LOG.debug("Applying patch %s in directory %s", p, working_dir)
            patch_contents = sh.load_file(p)
            if patch_contents:
                sh.execute(*PATCH_CMD, process_input=patch_contents)
