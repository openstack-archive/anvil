# From devstack commit b3288381047690510845209cc372d07e5b11e396

[pipeline:glance-registry]

#pipeline = context registryapp
# NOTE: use the following pipeline for keystone
pipeline = authtoken auth-context context registryapp

[app:registryapp]

paste.app_factory = glance.common.wsgi:app_factory
glance.app_factory = glance.registry.api.v1:API

[filter:context]

context_class = glance.registry.context.RequestContext
paste.filter_factory = glance.common.wsgi:filter_factory
glance.filter_factory = glance.common.context:ContextMiddleware

[filter:authtoken]

paste.filter_factory = keystone.middleware.auth_token:filter_factory

service_host = %KEYSTONE_SERVICE_HOST%
service_port = %KEYSTONE_SERVICE_PORT%
service_protocol = %KEYSTONE_SERVICE_PROTOCOL%

auth_host = %KEYSTONE_AUTH_HOST%
auth_port = %KEYSTONE_AUTH_PORT%
auth_protocol = %KEYSTONE_AUTH_PROTOCOL%
auth_uri = %KEYSTONE_SERVICE_PROTOCOL%://%KEYSTONE_SERVICE_HOST%:%KEYSTONE_SERVICE_PORT%/

admin_token = %SERVICE_TOKEN%
admin_tenant_name = %SERVICE_TENANT_NAME%
admin_user = %SERVICE_USERNAME%
admin_password = %SERVICE_PASSWORD%

[filter:auth-context]

context_class = glance.registry.context.RequestContext
paste.filter_factory = glance.common.wsgi:filter_factory
glance.filter_factory = keystone.middleware.glance_auth_token:KeystoneContextMiddleware



