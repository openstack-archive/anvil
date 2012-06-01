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

from anvil import colorizer
from anvil import importer
from anvil import log as logging
from anvil import utils

LOG = logging.getLogger(__name__)


class Initializer(object):

    def __init__(self, cfg):
        # Late load since its using a client lib that is only avail after install...
        self.cfg = cfg
        client_cls = importer.import_entry_point("keystoneclient.v2_0.client:Client")
        self.client = client_cls(token=self.cfg['service_token'],
            endpoint=self.cfg['endpoints']['admin']['uri'])

    def _create_tenants(self, tenants):
        tenants_made = dict()
        for entry in tenants:
            name = entry['name']
            if name in tenants_made:
                LOG.warn("Already created tenant %s", colorizer.quote(name))
            tenant = {
                'tenant_name': name,
                'description': entry['description'],
                'enabled': True,
            }
            LOG.debug("Creating tenant %s", tenant)
            tenants_made[name] = self.client.tenants.create(**tenant)
        return tenants_made

    def _create_users(self, users, tenants):
        created = dict()
        for entry in users:
            name = entry['name']
            if name in created:
                LOG.warn("Already created user %s", colorizer.quote(name))
            password = entry['password']
            email = entry['email']
            user = {
                'name': name,
                'password': password,
                'email': email,
            }
            LOG.debug("Creating user %s", user)
            created[name] = self.client.users.create(**user)
        return created

    def _create_roles(self, roles):
        roles_made = dict()
        for r in roles:
            role = r
            if role in roles_made:
                LOG.warn("Already created role %s", colorizer.quote(role))
            LOG.debug("Creating role %s", role)
            roles_made[role] = self.client.roles.create(role)
        return roles_made

    def _connect_roles(self, users, roles_made, tenants_made, users_made):
        roles_attached = set()
        for info in users:
            name = info['name']
            if name in roles_attached:
                LOG.warn("Already attached roles to user %s", colorizer.quote(name))
            roles_attached.add(name)
            user = users_made[name]
            for role_entry in info['roles']:
                # Role:Tenant
                (r, sep, t) = role_entry.partition(":")
                role_name = r
                tenant_name = t
                if not role_name or not tenant_name:
                    raise RuntimeError("Role or tenant name missing for user %s" % (name))
                if not role_name in roles_made:
                    raise RuntimeError("Role %s not previously created for user %s" % (role_name, name))
                if not tenant_name in tenants_made:
                    raise RuntimeError("Tenant %s not previously created for user %s" % (tenant_name, name))
                user_role = {
                    'user': user,
                    'role': roles_made[role_name],
                    'tenant': tenants_made[tenant_name],
                }
                LOG.debug("Creating user role %s", user_role)
                self.client.roles.add_user_role(**user_role)

    def _create_services(self, services):
        created_services = dict()
        for info in services:
            name = info['name']
            if name in created_services:
                LOG.warn("Already created service %s", colorizer.quote(name))
            service = {
                'name': name,
                'service_type': info['type'],
                'description': info.get('description') or ''
            }
            LOG.debug("Creating service %s", service)
            created_services[name] = self.client.services.create(**service)
        return created_services

    def _create_endpoints(self, endpoints, services):
        for entry in endpoints:
            name = entry['service']
            if name not in services:
                raise RuntimeError("Endpoint %s not attached to a previously created service" % (name))
            service = services[name]
            endpoint = {
                'region': entry['region'],
                'publicurl': entry['public_url'],
                'adminurl': entry['admin_url'],
                'internalurl': entry['internal_url'],
                'service_id': service.id,
            }
            LOG.debug("Creating endpoint %s", endpoint)
            self.client.endpoints.create(**endpoint)

    def initialize(self, users, tenants, roles, services, endpoints):
        created_tenants = self._create_tenants(tenants)
        created_users = self._create_users(users, created_tenants)
        created_roles = self._create_roles(roles)
        self._connect_roles(users, created_roles, created_tenants, created_users)
        services_made = self._create_services(services)
        self._create_endpoints(endpoints, services_made)


def get_shared_params(cfg, service_user=None):

    mp = dict()

    # Tenants and users
    mp['tenants'] = ['admin', 'service', 'demo']
    mp['users'] = ['admin', 'demo']

    mp['demo_tenant'] = 'demo'
    mp['demo_user'] = 'demo'

    mp['admin_tenant'] = 'admin'
    mp['admin_user'] = 'admin'

    mp['service_tenant'] = 'service'
    if service_user:
        mp['users'].append(service_user)
        mp['service_user'] = service_user

    # Tokens and passwords
    mp['service_token'] = cfg.get_password(
        "service_token",
        'the service admin token',
        )
    mp['admin_password'] = cfg.get_password(
        'horizon_keystone_admin',
        'the horizon and keystone admin',
        length=20,
        )
    mp['demo_password'] = mp['admin_password']
    mp['service_password'] = cfg.get_password(
        'service_password',
        'service authentication',
        )

    host_ip = cfg.get('host', 'ip')
    mp['service_host'] = host_ip

    # Components of the admin endpoint
    keystone_auth_host = cfg.getdefaulted('keystone', 'keystone_auth_host', host_ip)
    keystone_auth_port = cfg.getdefaulted('keystone', 'keystone_auth_port', '35357')
    keystone_auth_proto = cfg.getdefaulted('keystone', 'keystone_auth_protocol', 'http')
    keystone_auth_uri = utils.make_url(keystone_auth_proto,
                            keystone_auth_host, keystone_auth_port, path="v2.0")

    # Components of the public+internal endpoint
    keystone_service_host = cfg.getdefaulted('keystone', 'keystone_service_host', host_ip)
    keystone_service_port = cfg.getdefaulted('keystone', 'keystone_service_port', '5000')
    keystone_service_proto = cfg.getdefaulted('keystone', 'keystone_service_protocol', 'http')
    keystone_service_uri = utils.make_url(keystone_service_proto,
                            keystone_service_host, keystone_service_port, path="v2.0")

    mp['endpoints'] = {
        'admin': {
            'uri': keystone_auth_uri,
            'port': keystone_auth_port,
            'protocol': keystone_auth_proto,
            'host': keystone_auth_host,
        },
        'admin_templated': {
            'uri': utils.make_url(keystone_auth_proto,
                            keystone_auth_host, port='$(admin_port)s', path="v2.0"),
            'protocol': keystone_auth_proto,
            'host': keystone_auth_host,
        },
        'public': {
            'uri': keystone_service_uri,
            'port': keystone_service_port,
            'protocol': keystone_service_proto,
            'host': keystone_service_host,
        },
        'public_templated': {
            'uri': utils.make_url(keystone_service_proto,
                            keystone_service_host, port='$(public_port)s', path="v2.0"),
            'protocol': keystone_service_proto,
            'host': keystone_service_host,
        },
    }
    mp['endpoints']['internal'] = dict(mp['endpoints']['public'])
    mp['endpoints']['internal_templated'] = dict(mp['endpoints']['public_templated'])

    LOG.debug("Keystone shared params: %s", mp)
    return mp
