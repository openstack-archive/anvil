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
import logging
import os

from anvil import cfg_helpers 

LOG = logging.getLogger(__name__)


class InputPassword(object):
    def __init__(self, cfg):
        self.cfg = cfg

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


class ConfigPassword(object):
    def __init__(self, cfg):
        self.cfg = cfg

    def get_password(self, option, **kargs):
        return self.cfg.get(cfg_helpers.PW_SECTION, option)


class RandomPassword(object):
    def __init__(self, cfg):
        self.cfg = cfg

    def generate_random(self, length):
        """Returns a randomly generated password of the specified length."""
        LOG.debug("Generating a pseudo-random password of %d characters",
                  length)
        if length <= 0:
            return ''
        return binascii.hexlify(os.urandom((length + 1) / 2))[:length]

    def get_password(self, option, **kargs):
        return self.generate_random(int(kargs.get('length', 8)))
