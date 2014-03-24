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

# These map what action states will cause what other action states to be
# removed (aka the inverse operations of each state). This is used so that
# we can skip states that have already completed as well as redo states when
# the inverse is applied.
ACTIONS = {
    "configure": ["unconfigure"],
    "download": [],
    "download-patch": [],
    "package": ["package-destroy"],
    "package-destroy": ["package-install", "install", "package"],
    "package-install": ["package-uninstall", "uninstall", "package-destroy"],
    "package-install-all-deps": [],
    "package-uninstall": ["package-install", "package-install-all-deps"],
    "post-install": [],
    "post-start": [],
    "post-uninstall": ["pre-install", "post-install"],
    "pre-install": ["pre-uninstall", "post-uninstall"],
    "pre-start": [],
    "pre-uninstall": ["post-install"],
    "start": ["stopped"],
    "stopped": ["pre-start", "start", "post-start"],
    "unconfigure": ["configure"],
    "uninstall": ["prepare", "download", "download-patch"],
}
