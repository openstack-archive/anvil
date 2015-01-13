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

from anvil.actions import build
from anvil.actions import prepare


_NAMES_TO_RUNNER = {
    'build': build.BuildAction,
    'prepare': prepare.PrepareAction,
}
_RUNNER_TO_NAMES = dict((v, k) for k, v in _NAMES_TO_RUNNER.items())


def names():
    """Returns a list of the available action names."""
    return list(sorted(_NAMES_TO_RUNNER.keys()))


def class_for(action):
    """Given an action name, look up the factory for that action runner."""
    try:
        return _NAMES_TO_RUNNER[action]
    except KeyError:
        raise RuntimeError('Unrecognized action %s' % action)
