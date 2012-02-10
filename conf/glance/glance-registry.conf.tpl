## Based off of split glance-registry-paste.ini commit 30439a6dc4
## And split glance-registry.conf commit 30439a6dc4

[DEFAULT]
# Show more verbose log output (sets INFO log level output)
verbose = True

# Show debugging output in logs (sets DEBUG log level output)
debug = False

# Address to bind the registry server
bind_host = 0.0.0.0

# Port the bind the registry server to
bind_port = 9191

# Log to this file. Make sure you do not set the same log
# file for both the API and registry servers!
#log_file = %DEST%/glance/registry.log

# Where to store images
filesystem_store_datadir = %DEST%/glance/images

# Send logs to syslog (/dev/log) instead of to file specified by `log_file`
use_syslog = %SYSLOG%

# SQLAlchemy connection string for the reference implementation
# registry server. Any valid SQLAlchemy connection string is fine.
# See: http://www.sqlalchemy.org/docs/05/reference/sqlalchemy/connections.html#sqlalchemy.create_engine
sql_connection = %SQL_CONN%

# Period in seconds after which SQLAlchemy should reestablish its connection
# to the database.
#
# MySQL uses a default `wait_timeout` of 8 hours, after which it will drop
# idle connections. This can result in 'MySQL Gone Away' exceptions. If you
# notice this, you can lower this value to ensure that SQLAlchemy reconnects
# before MySQL can drop the connection.
sql_idle_timeout = 3600

# Limit the api to return `param_limit_max` items in a call to a container. If
# a larger `limit` query param is provided, it will be reduced to this value.
api_limit_max = 1000

# If a `limit` query param is not provided in an api request, it will
# default to `limit_param_default`
limit_param_default = 25


## SPLIT HERE ##
## SPLIT HERE ##
## SPLIT HERE ##

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

[filter:auth-context]
context_class = glance.registry.context.RequestContext
paste.filter_factory = glance.common.wsgi:filter_factory
glance.filter_factory = keystone.middleware.glance_auth_token:KeystoneContextMiddleware
