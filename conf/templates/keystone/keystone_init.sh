#!/bin/bash

# From devstack commit c4849e7f8f40f522541d8e1e03771edf942d851e with modifications

#
# Initial data for Keystone using python-keystoneclient
#
# A set of EC2-compatible credentials is created for both admin and demo
# users and placed in $DEVSTACK_DIR/ec2rc.
#
# Tenant               User      Roles
# -------------------------------------------------------
# admin                admin     admin
# service              glance    admin
# service              nova      admin
# service              quantum   admin        # if enabled
# service              swift     admin        # if enabled
# demo                 admin     admin
# demo                 demo      Member,sysadmin,netadmin
# invisible_to_admin   demo      Member
#
# Variables set before calling this script:
#
# SERVICE_TOKEN - aka admin_token in keystone.conf
# AUTH_ENDPOINT - local Keystone admin endpoint
# SERVICE_TENANT_NAME - name of tenant containing service accounts
# ENABLED_SERVICES - devstack's list of services being activated

set -e

ADMIN_PASSWORD=%ADMIN_PASSWORD%
export ADMIN_PASSWORD

SERVICE_PASSWORD=%SERVICE_PASSWORD%
export SERVICE_PASSWORD

SERVICE_TOKEN=%SERVICE_TOKEN%
export SERVICE_TOKEN

# This is really the AUTH_ENDPOINT (wtf)
SERVICE_ENDPOINT=%AUTH_ENDPOINT%
export SERVICE_ENDPOINT

SERVICE_TENANT_NAME=%SERVICE_TENANT_NAME%
export SERVICE_TENANT_NAME

function get_id () {
    echo `$@ | awk '/ id / { print $4 }'`
}

# Tenants
ADMIN_TENANT=$(get_id keystone tenant-create --name=admin)
SERVICE_TENANT=$(get_id keystone tenant-create --name=$SERVICE_TENANT_NAME)
DEMO_TENANT=$(get_id keystone tenant-create --name=demo)
INVIS_TENANT=$(get_id keystone tenant-create --name=invisible_to_admin)

# Users
ADMIN_USER=$(get_id keystone user-create --name=admin \
                                         --pass="$ADMIN_PASSWORD" \
                                         --email=admin@example.com)
DEMO_USER=$(get_id keystone user-create --name=demo \
                                        --pass="$ADMIN_PASSWORD" \
                                        --email=demo@example.com)

# Roles
ADMIN_ROLE=$(get_id keystone role-create --name=admin)
KEYSTONEADMIN_ROLE=$(get_id keystone role-create --name=KeystoneAdmin)
KEYSTONESERVICE_ROLE=$(get_id keystone role-create --name=KeystoneServiceAdmin)
SYSADMIN_ROLE=$(get_id keystone role-create --name=sysadmin)
NETADMIN_ROLE=$(get_id keystone role-create --name=netadmin)

# Add Roles to Users in Tenants
keystone user-role-add --user $ADMIN_USER --role $ADMIN_ROLE --tenant_id $ADMIN_TENANT 2>&1 >/dev/null
keystone user-role-add --user $ADMIN_USER --role $ADMIN_ROLE --tenant_id $DEMO_TENANT 2>&1 >/dev/null
keystone user-role-add --user $DEMO_USER --role $SYSADMIN_ROLE --tenant_id $DEMO_TENANT 2>&1 >/dev/null
keystone user-role-add --user $DEMO_USER --role $NETADMIN_ROLE --tenant_id $DEMO_TENANT 2>&1 >/dev/null

# TODO(termie): these two might be dubious
keystone user-role-add --user $ADMIN_USER --role $KEYSTONEADMIN_ROLE --tenant_id $ADMIN_TENANT 2>&1 >/dev/null
keystone user-role-add --user $ADMIN_USER --role $KEYSTONESERVICE_ROLE --tenant_id $ADMIN_TENANT 2>&1 >/dev/null

# The Member role is used by Horizon and Swift so we need to keep it:
MEMBER_ROLE=$(get_id keystone role-create --name=Member)
keystone user-role-add --user $DEMO_USER --role $MEMBER_ROLE --tenant_id $DEMO_TENANT 2>&1 >/dev/null
keystone user-role-add --user $DEMO_USER --role $MEMBER_ROLE --tenant_id $INVIS_TENANT 2>&1 >/dev/null

# Services
keystone service-create --name=keystone --type=identity --description="Keystone Identity Service" 2>&1 >/dev/null

keystone service-create --name=nova --type=compute --description="Nova Compute Service" 2>&1 >/dev/null

NOVA_USER=$(get_id keystone user-create --name=nova --pass="$SERVICE_PASSWORD" \
                --tenant_id $SERVICE_TENANT --email=nova@example.com)

keystone user-role-add --tenant_id $SERVICE_TENANT --user $NOVA_USER  --role $ADMIN_ROLE 2>&1 >/dev/null

keystone service-create --name=ec2 --type=ec2 --description="EC2 Compatibility Layer" 2>&1 >/dev/null

keystone service-create --name=glance  --type=image  --description="Glance Image Service" 2>&1 >/dev/null
                        
GLANCE_USER=$(get_id keystone user-create --name=glance  --pass="$SERVICE_PASSWORD" \
                            --tenant_id $SERVICE_TENANT   --email=glance@example.com)

keystone user-role-add --tenant_id $SERVICE_TENANT --user $GLANCE_USER --role $ADMIN_ROLE 2>&1 >/dev/null

keystone service-create --name="nova-volume"  --type=volume  --description="Nova Volume Service" 2>&1 >/dev/null

if [[ "$ENABLED_SERVICES" =~ "swift" ]]; then
    keystone service-create --name=swift --type="object-store" --description="Swift Service" 2>&1 >/dev/null
    SWIFT_USER=$(get_id keystone user-create --name=swift \
                                             --pass="$SERVICE_PASSWORD" \
                                             --tenant_id $SERVICE_TENANT \
                                             --email=swift@example.com)
    keystone user-role-add --tenant_id $SERVICE_TENANT  --user $SWIFT_USER  --role $ADMIN_ROLE 2>&1 >/dev/null
fi

if [[ "$ENABLED_SERVICES" =~ "quantum-server" ]]; then
    keystone service-create --name=quantum  --type=network  --description="Quantum Service" 2>&1 >/dev/null
    QUANTUM_USER=$(get_id keystone user-create --name=quantum \
                                               --pass="$SERVICE_PASSWORD" \
                                               --tenant_id $SERVICE_TENANT \
                                               --email=quantum@example.com)
    keystone user-role-add --tenant_id $SERVICE_TENANT  --user $QUANTUM_USER  --role $ADMIN_ROLE 2>&1 >/dev/null
fi

# create ec2 creds and parse the secret and access key returned
RESULT=$(keystone ec2-credentials-create --tenant_id=$ADMIN_TENANT --user=$ADMIN_USER)
ADMIN_ACCESS=$(echo "$RESULT" | awk '/ access / { print $4 }')
ADMIN_SECRET=$(echo "$RESULT" | awk '/ secret / { print $4 }')

RESULT=$(keystone ec2-credentials-create --tenant_id=$DEMO_TENANT --user=$DEMO_USER)
DEMO_ACCESS=$(echo "$RESULT" | awk '/ access / { print $4 }')
DEMO_SECRET=$(echo "$RESULT" | awk '/ secret / { print $4 }')

cat <<EOF
# EC2 access variables (ie for euca tools...)
export EC2_ACCESS_KEY=$DEMO_ACCESS
export EC2_SECRET_KEY=$DEMO_SECRET

# Not really EC2 but useful for knowing...
export ADMIN_SECRET=$ADMIN_SECRET
export ADMIN_ACCESS=$ADMIN_ACCESS
export DEMO_ACCESS=$DEMO_ACCESS
export DEMO_SECRET=$DEMO_SECRET
EOF
