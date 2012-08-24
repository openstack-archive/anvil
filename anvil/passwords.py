# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#    Copyright (C) 2012 New Dream Network, LLC (DreamHost) All Rights Reserved.
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
import os

from anvil import log as logging

LOG = logging.getLogger(__name__)


class ProxyPassword(object):
    def __init__(self, cache=None):
        if cache is None:
            self.cache = {}
        else:
            self.cache = cache
        self.resolvers = []

    def _valid_password(self, pw):
        if pw is None:
            return False
        if len(pw) > 0:
            return True
        return False

    def get_password(self, option, prompt_text='', length=8, **kwargs):
        if option in self.cache:
            return self.cache[option]
        password = ''
        for resolver in self.resolvers:
            found_password = resolver.get_password(option,
                                                   prompt_text=prompt_text,
                                                   length=length, **kwargs)
            if self._valid_password(found_password):
                password = found_password
                break
        if len(password) == 0:
            LOG.warn("Password provided for %r is empty", option)
        self.cache[option] = password
        return password


class InputPassword(object):
    def _valid_password(self, pw):
        cleaned_pw = pw.strip()
        if len(cleaned_pw) == 0:
            return False
        else:
            return True

    def _prompt_user(self, prompt_text):
        LOG.debug('Asking the user for a %r password', prompt_text)
        message = ("Enter a password to use for %s "
                   "[or press enter to get a generated one]: " % prompt_text
                   )
        rc = ""
        while True:
            rc = getpass.getpass(message)
            # Length zero seems to mean just enter was pressed (which means skip in our case)
            if len(rc) == 0 or self._valid_password(rc):
                break
            else:
                LOG.warn("Invalid password %r (please try again)" % (rc))
        return rc

    def get_password(self, option, **kargs):
        return self._prompt_user(kargs.get('prompt_text', '??'))


class RandomPassword(object):
    def generate_random(self, length):
        """Returns a randomly generated password of the specified length."""
        LOG.debug("Generating a pseudo-random password of %d characters",
                  length)
        if length <= 0:
            return ''
        return binascii.hexlify(os.urandom((length + 1) / 2))[:length]

    def get_password(self, option, **kargs):
        return self.generate_random(int(kargs.get('length', 8)))
