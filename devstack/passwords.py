#!/usr/bin/env python

import ConfigParser
import binascii
import getpass
import logging
import os
import re

from devstack.cfg import make_id

LOG = logging.getLogger("devstack.passwords")


def generate_random(length):
    """Returns a randomly generated password of the specified length."""
    LOG.debug("Generating a pseudo-random password of %d characters",
              length)
    return binascii.hexlify(os.urandom((length + 1) / 2))[:length]


class PasswordGenerator(object):

    def __init__(self, cfg, prompt_user=True):
        self.cfg = cfg
        self.prompt_user = prompt_user
        # Store the values accessed by the caller
        # so the main script can print them out
        # at the end.
        self.accessed = {}

    def _prompt_user(self, prompt_text):
        LOG.debug('Asking the user for a %r password', prompt_text)
        message = ("Enter a password to use for %s "
                   "[or press enter to get a generated one] " % prompt_text
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

    # FIXME: Remove the "section" argument, since it is always the same.
    def get_password(self, section, option, prompt_text, length=8):
        """Returns a password identified by the configuration location."""
        LOG.debug('Looking for password %s (%s)', option, prompt_text)

        # Look in the configuration file(s)
        try:
            password = self.cfg.get(section, option)
        except ConfigParser.Error:
            password = ''

        # Optionally ask the user
        if not password and self.prompt_user:
            password = self._prompt_user(prompt_text)
            self.accessed[make_id(section, option)] = password

        # If we still don't have a value, make one up.
        if not password:
            LOG.debug('No configured password for %s (%s)',
                      option, prompt_text)
            password = generate_random(length)

        # Update the configration cache so that other parts of the
        # code can find the value.
        self.cfg.set(section, option, password)
        return password
