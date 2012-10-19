#!/usr/bin/env python

from optparse import OptionParser

import getpass
import os
import sys

possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))

if os.path.exists(os.path.join(possible_topdir,
                               'anvil',
                               '__init__.py')):
    sys.path.insert(0, possible_topdir)


from anvil import log as logging
from anvil.components.helpers import glance

from anvil import passwords


def get_password(user):
    pw_storage = passwords.KeyringProxy(path='/etc/anvil/passwords.cfg')
    lookup_name = "%s_password" % (user)
    prompt = "Please enter the keystone password for user %s: " % (user)
    (exists, pw) = pw_storage.read(lookup_name, prompt)
    if not exists:
        pw_storage.save(lookup_name, pw)
    return pw


def main():
    parser = OptionParser()
    parser.add_option("-u", '--user', dest='user',
                      help='user to upload the image/s as', metavar='USER')
    parser.add_option("-t", '--tenant', dest='tenant',
                      help='tenant to upload the image/s as', metavar='TENANT')
    parser.add_option("-g", '--glance', dest='glance_uri',
                      help='glance endpoint uri to upload to', metavar='GLANCE')
    parser.add_option("-k", '--keystone', dest='keystone_uri',
                      help='keystone endpoint uri to authenticate with', metavar='KEYSTONE')
    parser.add_option('-i', '--image', dest='images',
                      action='append', help="image archive file or uri to upload to glance")
    (options, args) = parser.parse_args()
    # Why can't i iterate over this, sad...
    if (not options.user or not options.tenant or not options.glance_uri
        or not options.keystone_uri or not options.images):
        parser.error("options are missing, please try -h")
    logging.setupLogging(logging.DEBUG)
    params = {
        'keystone': {
            'admin_tenant': options.tenant,
            'admin_user': options.user,
            'admin_password': get_password(options.user),
            'endpoints': {
                'public': {
                    'uri': options.keystone_uri,
                },
            },
        },
        'glance': {
            'endpoints': {
                'public': {
                    'uri': options.glance_uri,
                },
            },
        },
    }
    img_am = len(options.images)
    uploader = glance.UploadService(params)
    am_installed = uploader.install(options.images)
    if img_am == am_installed:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
