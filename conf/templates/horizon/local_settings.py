#* 
   This is a cheetah template!
*#

# These settings are good for dev-like environments (or ci)
# When moving to production it is likely some more thought should
# be given here... 
#
# See: https://docs.djangoproject.com/en/dev/ref/settings/
#
# This file overrides other defaults in openstack_dashboard/settings.py

import os

DEBUG = True
TEMPLATE_DEBUG = DEBUG
PROD = False
USE_SSL = False

LOCAL_PATH = os.path.dirname(os.path.abspath(__file__))

# See: https://docs.djangoproject.com/en/dev/topics/cache/?from=olddocs
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Use session cookies for any user-specific horizon session data
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

# Send email to the console by default
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# See: https://code.google.com/p/django-mailer/
#
# django-mailer uses a different settings attribute
MAILER_EMAIL_BACKEND = EMAIL_BACKEND

# Set a secure and unique SECRET_KEY (the Django default is '')
#
# See: https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-SECRET_KEY
SECRET_KEY = "${SECRET_KEY}"

# The OPENSTACK_KEYSTONE_BACKEND settings can be used to identify the
# capabilities of the auth backend for Keystone.
# If Keystone has been configured to use LDAP as the auth backend then set
# can_edit_user to False and name to 'ldap'.
#
# TODO(tres): Remove these once Keystone has an API to identify auth backend.
OPENSTACK_KEYSTONE_BACKEND = {
    'name': 'native',
    'can_edit_user': True
}

OPENSTACK_HOST = "${OPENSTACK_HOST}"
OPENSTACK_KEYSTONE_URL = "http://%s:5000/v2.0" % OPENSTACK_HOST
OPENSTACK_KEYSTONE_DEFAULT_ROLE = "Member"

# The timezone of the server. This should correspond with the timezone
# of your entire OpenStack installation, and hopefully be in UTC.
TIME_ZONE = "UTC"

LOGGING = {
    'version': 1,
    # When set to True this will disable all logging except
    # for loggers specified in this configuration dictionary. Note that
    # if nothing is specified here and disable_existing_loggers is True,
    # django.db.backends will still log unless it is disabled explicitly.
    'disable_existing_loggers': False,
    'handlers': {
        'null': {
            'level': 'DEBUG',
            'class': 'django.utils.log.NullHandler',
        },
        'console': {
            # Set the level to "DEBUG" for verbose output logging.
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
     },
    'loggers': {
        # Logging from django.db.backends is VERY verbose, send to null
        # by default.
        'django.db.backends': {
            'handlers': ['null'],
            'propagate': False,
        },
        'horizon': {
            'handlers': ['console'],
            'propagate': False,
        },
        'openstack_dashboard': {
            'handlers': ['console'],
            'propagate': False,
        },
        'novaclient': {
            'handlers': ['console'],
            'propagate': False,
        },
        'keystoneclient': {
            'handlers': ['console'],
            'propagate': False,
        },
        'glanceclient': {
            'handlers': ['console'],
            'propagate': False,
        },
        'nose.plugins.manager': {
            'handlers': ['console'],
            'propagate': False,
        },
    },
}

