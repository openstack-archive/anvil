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

from keyring.backend import CryptedFileKeyring
from keyring.backend import UncryptedFileKeyring
from keyring.util import properties

from anvil import log as logging
from anvil import shell as sh
from anvil import utils

LOG = logging.getLogger(__name__)
RAND_PW_LEN = 20
PW_USER = 'anvil'

# There is some weird issue fixed after 0.9.2
# this applies that fix for us for now (taken from the trunk code)...
class FixedCryptedFileKeyring(CryptedFileKeyring):

    @properties.NonDataProperty
    def keyring_key(self):
        # _unlock or _init_file will set the key or raise an exception
        if self._check_file():
            self._unlock()
        else:
            self._init_file()
        return self.keyring_key


class KeyringProxy(object):
    def __init__(self, path, keyring_encrypted=False, enable_prompt=True, random_on_empty=True):
        self.path = path
        self.keyring_encrypted = keyring_encrypted
        if keyring_encrypted:
            self.ring = FixedCryptedFileKeyring()
        else:
            self.ring = UncryptedFileKeyring()
        self.ring.file_path = path
        self.enable_prompt = enable_prompt
        self.random_on_empty = random_on_empty

    def read(self, name, prompt):
        pw_val = self.ring.get_password(name, PW_USER)
        if pw_val:
            return (True, pw_val)
        pw_val = ''
        if self.enable_prompt and prompt:
            pw_val = InputPassword().get_password(name, prompt)
        if self.random_on_empty and len(pw_val) == 0:
            pw_val = RandomPassword().get_password(name, RAND_PW_LEN)
        return (False, pw_val)
    
    def save(self, name, password):
        self.ring.set_password(name, PW_USER, password)

    def __str__(self):
        prefix = 'encrypted'
        if not self.keyring_encrypted:
            prefix = "un" + prefix
        return '%s keyring @ %s' % (prefix, self.path)


class InputPassword(object):
    def _valid_password(self, pw):
        cleaned_pw = pw.strip()
        if len(cleaned_pw) == 0:
            return False
        else:
            return True

    def _prompt_user(self, prompt_text):
        prompt_text = prompt_text.strip()
        message = ("Enter a secret to use for the %s "
                   "[or press enter to get a generated one]: " % prompt_text
                   )
        rc = ""
        while True:
            rc = getpass.getpass(message)
            # Length zero seems to mean just enter was pressed (which means skip in our case)
            if len(rc) == 0 or self._valid_password(rc):
                break
            else:
                LOG.warn("Invalid secret %r (please try again)" % (rc))
        return rc

    def get_password(self, option, prompt_text):
        return self._prompt_user(prompt_text)


class RandomPassword(object):
    def generate_random(self, length):
        """Returns a randomly generated password of the specified length."""
        LOG.debug("Generating a pseudo-random secret of %d characters", length)
        if length <= 0:
            return ''
        return binascii.hexlify(os.urandom((length + 1) / 2))[:length]

    def get_password(self, option, length):
        return self.generate_random(int(length))
