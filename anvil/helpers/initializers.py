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

    def __init__(self, cfg):
        self.replacements = dict()
        self.replacements['keystone'] = keystone.get_shared_params(cfg)
        self.replacements['glance'] = glance.get_shared_params(cfg)
        self.replacements['SERVICE_HOST'] = cfg.get('host', 'ip')
        self.client = key_client.Client(token=self.replacements['keystone']['service_token'],
            endpoint=self.replacements['keystone']['endpoints']['admin']['uri'])

    def _do_replace(self, text):
        return utils.param_replace(text, self.replacements, ignore_missing=True)

    def _create_tenants(self, tenants):
        tenants_made = dict()
        for entry in tenants:
            name = entry['name']
            if name in tenants_made:
                raise RuntimeError("Already created tenant %s" % (name))
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
                raise RuntimeError("Already created user %s" % (name))
            password = self._do_replace(entry['password'])
            email = entry.get('email', "none@none.com")
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
            if role in roles_made:
                raise RuntimeError("Already created role %s" % (role))
            LOG.debug("Creating role %s", role)
            roles_made[role] = self.client.roles.create(role)
        return roles_made

    def _connect_roles(self, users, roles_made, tenants_made, users_made):
        roles_attached = set()
        for info in users:
            name = info['name']
            if name in roles_attached:
                raise RuntimeError("Already attached roles to user %s" % (name))
            roles_attached.add(name)
            user = users_made[name]
            for role_entry in info['roles']:
                (role_name, sep, tenant_name) = role_entry.partition(":")
                if not role_name or not tenant_name:
                    raise RuntimeError("Role or tenant name missing for user %s" % (name))
                if not role_name in roles_made:
                    LOG.warn("Role %s not previously created for user %s", role_name, name)
                if not tenant_name in tenants_made:
                    LOG.warn("Tenant %s not previously created for user %s", tenant_name, name)
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
                raise RuntimeError("Already created service %s" % (name))
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
