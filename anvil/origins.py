# -*- coding: utf-8 -*-

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

import os

import jsonpatch

from anvil import utils


class Origin(dict):
    def __init__(self, filename, patched=False):
        super(Origin, self).__init__()
        self.filename = filename
        self.patched = patched
        self.release = os.path.basename(filename).split("-")[0]


def load(filename, patch_file=None):
    base = utils.load_yaml(filename)
    patched = False
    if patch_file:
        patch = jsonpatch.JsonPatch(patch_file)
        patch.apply(base, in_place=True)
        patched = True
    origin = Origin(filename, patched=patched)
    origin.update(base)
    return origin
