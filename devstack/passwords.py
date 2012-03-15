# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#    Copyright (C) 2012 Dreamhost Inc. All Rights Reserved.
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

import binascii
import getpass
import logging
import os
import re

LOG = logging.getLogger("devstack.passwords")
PW_SECTION = 'passwords'
HELPFUL_DESCRIPTIONS = {
    'sql': 'the database user',
    'rabbit': 'the rabbit user',
    'horizon_keystone_admin': 'the horizon and keystone admin',
    'service_password': 'service authentication',
    "service_token": 'the service admin token',
}


def get_pw_usage(option):
    return HELPFUL_DESCRIPTIONS.get(option, '???')


def generate_random(length):
    """Returns a randomly generated password of the specified length."""
    LOG.debug("Generating a pseudo-random password of %d characters",
              length)
    return binascii.hexlify(os.urandom((length + 1) / 2))[:length]


class PasswordGenerator(object):

    def __init__(self, cfg, prompt_user=True):
        self.cfg = cfg
        self.prompt_user = prompt_user

    def _valid_password(self, pw):
        # FIXME: More efficient way to look for whitespace?
        if re.match(r"^(\s+)$", pw) or \
                re.match(r"^(\s+)(\S+)(\s+)$", pw) or \
                re.match(r"^(\S+)(\s+)$", pw) or \
                re.match(r"^(\s+)(\S+)$", pw):
            return False
        return True

    def _prompt_user(self, prompt_text):
        LOG.debug('Asking the user for a %r password', prompt_text)
        message = ("Enter a password to use for %s "
                   "[or press enter to get a generated one]: " % prompt_text
                   )
        rc = ""
        while True:
            rc = getpass.getpass(message)
            if len(rc) == 0 or self._valid_password(rc):
                break
            else:
                LOG.warn("Invalid password \"%s\" (please try again)" % (rc))
        return rc

    def extract(self, option):
        return self.cfg.get(PW_SECTION, option)

    def _set_through(self, option, value):
        self.cfg.set(PW_SECTION, option, value)

    def get_password(self, option, prompt_text=None, length=8):
        """Returns a password identified by the configuration location."""

        if not prompt_text:
            prompt_text = get_pw_usage(option)

        LOG.debug('Looking for password %s (%s)', option, prompt_text)

        # Look in the configuration file(s)
        password = None
        from_config = False
        if not password:
            password = self.cfg.get(PW_SECTION, option)
            if password:
                from_config = True

        # Optionally ask the user
        if not password and self.prompt_user:
            password = self._prompt_user(prompt_text)

        # If we still don't have a value, make one up.
        if not password:
            LOG.debug('No configured password for %s (%s)',
                      option, prompt_text)
            password = generate_random(length)

        # Update via set through to the config
        if not from_config:
            self._set_through(option, password)

        return password
