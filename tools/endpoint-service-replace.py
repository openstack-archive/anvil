#!/usr/bin/env python

from optparse import OptionParser

import getpass
import os
import sys
import yaml

possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))

if os.path.exists(os.path.join(possible_topdir,
                               'anvil',
                               '__init__.py')):
    sys.path.insert(0, possible_topdir)


from anvil import log as logging
from anvil import importer
from anvil import passwords
from anvil.components.helpers import keystone
from anvil import utils


def get_token():
    pw_storage = passwords.KeyringProxy(path='/etc/anvil/passwords.cfg')
    lookup_name = "service_token"
    prompt = "Please enter the password for %s: " % ('/etc/anvil/passwords.cfg')
    (exists, token) = pw_storage.read(lookup_name, prompt)
    if not exists:
        pw_storage.save(lookup_name, token)
    return token


def replace_services_endpoints(token, options):
    client = importer.construct_entry_point("keystoneclient.v2_0.client:Client",
                                             token=token, endpoint=options.keystone_uri)
    current_endpoints = client.endpoints.list()
    current_services = client.services.list()

    def filter_resource(r):
        raw = dict(r.__dict__) # Can't access the raw attrs, arg...
        raw_cleaned = {}
        for k, v in raw.items():
            if k == 'manager' or k.startswith('_'):
                continue
            raw_cleaned[k] = v
        return raw_cleaned

    for e in current_endpoints:
        print("Deleting endpoint: ")
        print(utils.prettify_yaml(filter_resource(e)))
        client.endpoints.delete(e.id)

    for s in current_services:
        print("Deleting service: ")
        print(utils.prettify_yaml(filter_resource(s)))
        client.services.delete(s.id)

    if options.file:
        with(open(options.file, 'r')) as fh:
            contents = yaml.load(fh)
        set_contents = {
            'services': contents.get('services', []),
            'endpoints': contents.get('endpoints', []),
        }
        print("Regenerating with:")
        print(utils.prettify_yaml(set_contents))
        set_contents['users'] = []
        set_contents['roles'] = []
        set_contents['tenants'] = []
        initer = keystone.Initializer(token, options.keystone_uri)
        initer.initialize(**set_contents)


def main():
    parser = OptionParser()
    parser.add_option("-k", '--keystone', dest='keystone_uri',
                      help='keystone endpoint uri to authenticate with', metavar='KEYSTONE')
    parser.add_option("-f", '--file', dest='file',
                      help='service and endpoint creation file', metavar='FILE')
    (options, args) = parser.parse_args()
    if not options.keystone_uri or not options.file:
        parser.error("options are missing, please try -h")
    logging.setupLogging(logging.DEBUG)
    replace_services_endpoints(get_token(), options)


if __name__ == "__main__":
    sys.exit(main())
