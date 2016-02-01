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
PATCH_CMD = ['patch', '-p1']
GIT_PATCH_CMD = ['git', 'am']


def _is_patch(path, patch_ext='.patch'):
    if not path.endswith(patch_ext):
        return False
    if not sh.isfile(path):
        return False
    return True


def expand_patches(paths, patch_ext='.patch'):
    if not paths:
        return []
    all_paths = []
    # Expand patch files/dirs
    for path in paths:
        path = sh.abspth(path)
        if sh.isdir(path):
            all_paths.extend([p for p in sh.listdir(path, files_only=True)])
        else:
            all_paths.append(path)
    # Now filter on valid patches
    return [p for p in all_paths if _is_patch(p, patch_ext=patch_ext)]


def apply_patches(patch_files, working_dir):
    if not sh.isdir(working_dir):
        LOG.warning("Can only apply patches 'inside' a directory and not '%s'",
                 working_dir)
        return
    already_applied = set()
    for patch_ext, patch_cmd in [('.patch', PATCH_CMD), ('.git_patch', GIT_PATCH_CMD)]:
        apply_files = expand_patches(patch_files, patch_ext=patch_ext)
        apply_files = [p for p in apply_files if p not in already_applied]
        if not apply_files:
            continue
        with utils.chdir(working_dir):
            for p in apply_files:
                LOG.debug("Applying patch %s using command %s in directory %s",
                          p, patch_cmd, working_dir)
                patch_contents = sh.load_file(p)
                if len(patch_contents):
                    sh.execute(patch_cmd, process_input=patch_contents)
                already_applied.add(p)
