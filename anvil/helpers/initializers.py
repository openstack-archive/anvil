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


import weakref

from anvil import log as logging
from anvil import utils

from anvil.components import glance
from anvil.components import keystone

from keystoneclient.v2_0 import client as key_client

LOG = logging.getLogger(__name__)


class Keystone(object):

    def __init__(self, owner):
        self.owner = weakref.proxy(owner)
        self.replacements = dict()
        self.replacements.update(keystone.get_shared_params(self.owner.cfg, self.owner.pw_gen))
        self.replacements.update(glance.get_shared_params(self.owner.cfg))
        self.replacements['SERVICE_HOST'] = owner.cfg.get('host', 'ip')
        self.client = key_client.Client(token=self.replacements['SERVICE_TOKEN'],
                                        endpoint=self.replacements['AUTH_ENDPOINT'])

    def _do_replace(self, text):
        return utils.param_replace(text, self.replacements, ignore_missing=True)
        
    def _create_tenants(self, tenants):
        tenants_made = dict()
        for (name, desc) in tenants.items():
            tenant = {
                'tenant_name': name,
                'description': desc,
                'enabled': True,
            }
            LOG.debug("Creating tenant %s", tenant)
            tenants_made[name] = self.client.tenants.create(**tenant)
        return tenants_made

    def _create_users(self, users, tenants):
        created = dict()
        for (name, info) in users.items():
            password = self._do_replace(info['password'])
            email = info.get('email', "none@none.com")
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
        for role in roles:
            LOG.debug("Creating role %s", role)
            roles_made[role] = self.client.roles.create(role)
        return roles_made
    
    def _connect_roles(self, users, roles_made, tenants_made, users_made):
        for name, info in users.items():
            user = users_made[name]
            for role_entry in info['roles']:
                (role_name, sep, tenant_name) = role_entry.partition(":")
                user_role = {
                    'user': user,
                    'role': roles_made[role_name],
                    'tenant': tenants_made[tenant_name],
                }
                LOG.debug("Creating user role %s", user_role)
                self.client.roles.add_user_role(**user_role)

    def _create_services(self, services):
        created_services = dict()
        for (name, info) in services.items():
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
            service = services[entry['service']]
            endpoint = {
                'region': entry['region'],
                'publicurl': self._do_replace(entry['public_url']),
                'adminurl': self._do_replace(entry['admin_url']),
                'internalurl': self._do_replace(entry['internal_url']),
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
