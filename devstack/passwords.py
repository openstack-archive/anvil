#!/usr/bin/env python

import ConfigParser
import binascii
import getpass
import logging
import os
import re

from devstack import cfg_helpers

LOG = logging.getLogger("devstack.passwords")
PW_SECTION = 'passwords'
HELPFUL_DESCRIPTIONS = {
    'sql': 'the database user',
}


def get_pw_usage(option):
    return HELPFUL_DESCRIPTIONS.get(option, '???')


def generate_random(length):
    """Returns a randomly generated password of the specified length."""
    LOG.debug("Generating a pseudo-random password of %d characters",
              length)
    return binascii.hexlify(os.urandom((length + 1) / 2))[:length]


class PasswordGenerator(object):

    def __init__(self, kv_cache, cfg,
                    prompt_user=True):
        self.cfg = cfg
        self.config_cache = kv_cache
        self.prompt_user = prompt_user

    def _prompt_user(self, prompt_text):
        LOG.debug('Asking the user for a %r password', prompt_text)
        message = ("Enter a password to use for %s "
                   "[or press enter to get a generated one]: " % prompt_text
                   )
        rc = ""
        while True:
            rc = getpass.getpass(message)
            if len(rc) == 0:
                break
            # FIXME: More efficient way to look for whitespace?
            if re.match(r"^(\s+)$", rc):
                LOG.warning("Whitespace not allowed as a password!")
            elif re.match(r"^(\s+)(\S+)(\s+)$", rc) or \
                re.match(r"^(\S+)(\s+)$", rc) or \
                re.match(r"^(\s+)(\S+)$", rc):
                LOG.warning("Whitespace can not start or end a password!")
            else:
                break
        return rc

    def get_password(self, option, prompt_text=None, length=8):
        """Returns a password identified by the configuration location."""

        if not prompt_text:
            prompt_text = get_pw_usage(option)

        LOG.debug('Looking for password %s (%s)', option, prompt_text)

        cache_key = cfg_helpers.make_id(PW_SECTION, option)
        password = self.config_cache.get(cache_key)

        # Look in the configuration file(s)
        if not password:
            try:
                password = self.cfg.get(PW_SECTION, option)
            except ConfigParser.Error:
                password = ''

        # Optionally ask the user
        if not password and self.prompt_user:
            password = self._prompt_user(prompt_text)

        # If we still don't have a value, make one up.
        if not password:
            LOG.debug('No configured password for %s (%s)',
                      option, prompt_text)
            password = generate_random(length)

        # Update the cache so that other parts of the
        # code can find the value.
        self.config_cache[cache_key] = password

        return password
