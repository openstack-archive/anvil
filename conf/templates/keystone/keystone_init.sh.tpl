#!/bin/bash

# From devstack commit 5f9473e8b9bdc15f42db597d5d1e766b760f764e with some modifications
set -o errexit

# These are used by keystone commands below
export SERVICE_TOKEN=%SERVICE_TOKEN%

# This is really the auth endpoint, not the service endpoint
export SERVICE_ENDPOINT=%AUTH_ENDPOINT%

function get_id () {
    echo `$@ | grep ' id ' | awk '{print $4}'`
}

# Added! (NOT IN ORIGINAL)
ADMIN_USERNAME=%ADMIN_USER_NAME%
ADMIN_PASSWORD=%ADMIN_PASSWORD%
DEMO_USER_NAME=%DEMO_USER_NAME%
INVIS_USER_NAME=%INVIS_USER_NAME%
MEMBER_ROLE_NAME=Member
KEYSTONE_ADMIN_ROLE_NAME=KeystoneAdmin
KEYSTONE_SERVICE_ADMIN_ROLE_NAME=KeystoneServiceAdmin
SYSADMIN_ROLE_NAME=sysadmin
NETADMIN_ROLE_NAME=netadmin
DUMMY_EMAIL=admin@example.com

# Tenants (names are same as user names)
ADMIN_TENANT=`get_id keystone tenant-create --name=$ADMIN_USERNAME`
DEMO_TENANT=`get_id keystone tenant-create --name=$DEMO_USER_NAME`
INVIS_TENANT=`get_id keystone tenant-create --name=$INVIS_USER_NAME`

# Users
ADMIN_USER=`get_id keystone user-create \
                                 --name=$ADMIN_USERNAME \
                                 --pass="$ADMIN_PASSWORD" \
                                 --email=$DUMMY_EMAIL`

DEMO_USER=`get_id keystone user-create \
                                 --name=$DEMO_USER_NAME \
                                 --pass="$ADMIN_PASSWORD" \
                                 --email=$DUMMY_EMAIL`

# Detect if the keystone cli binary has the command names changed
# in https://review.openstack.org/4375
# FIXME(dtroyer): Remove the keystone client command checking
#                 after a suitable transition period.  add-user-role
#                 and ec2-create-credentials were renamed
if keystone help | grep -q user-role-add; then
    KEYSTONE_COMMAND_4375=1
fi

# Roles
ADMIN_ROLE=`get_id keystone role-create --name=$ADMIN_USERNAME`
MEMBER_ROLE=`get_id keystone role-create --name=$MEMBER_ROLE_NAME`
KEYSTONEADMIN_ROLE=`get_id keystone role-create --name=$KEYSTONE_ADMIN_ROLE_NAME`
KEYSTONESERVICE_ROLE=`get_id keystone role-create --name=$KEYSTONE_SERVICE_ADMIN_ROLE_NAME`
SYSADMIN_ROLE=`get_id keystone role-create --name=$SYSADMIN_ROLE_NAME`
NETADMIN_ROLE=`get_id keystone role-create --name=$NETADMIN_ROLE_NAME`

# Added 2>&1 >/dev/null to all (NOT IN ORIGINAL)

if [[ -n "$KEYSTONE_COMMAND_4375" ]]; then
    # Add Roles to Users in Tenants
    keystone user-role-add --user $ADMIN_USER --role $ADMIN_ROLE --tenant_id $ADMIN_TENANT 2>&1 >/dev/null
    keystone user-role-add --user $DEMO_USER --role $MEMBER_ROLE --tenant_id $DEMO_TENANT 2>&1 >/dev/null 
    keystone user-role-add --user $DEMO_USER --role $SYSADMIN_ROLE --tenant_id $DEMO_TENANT 2>&1 >/dev/null
    keystone user-role-add --user $DEMO_USER --role $NETADMIN_ROLE --tenant_id $DEMO_TENANT 2>&1 >/dev/null
    keystone user-role-add --user $DEMO_USER --role $MEMBER_ROLE --tenant_id $INVIS_TENANT 2>&1 >/dev/null
    keystone user-role-add --user $ADMIN_USER --role $ADMIN_ROLE --tenant_id $DEMO_TENANT 2>&1 >/dev/null

    # TODO(termie): these two might be dubious
    keystone user-role-add --user $ADMIN_USER --role $KEYSTONEADMIN_ROLE --tenant_id $ADMIN_TENANT 2>&1 >/dev/null
    keystone user-role-add --user $ADMIN_USER --role $KEYSTONESERVICE_ROLE --tenant_id $ADMIN_TENANT 2>&1 >/dev/null
else
    ### compat
    # Add Roles to Users in Tenants
    keystone add-user-role $ADMIN_USER $ADMIN_ROLE $ADMIN_TENANT 2>&1 >/dev/null
    keystone add-user-role $DEMO_USER $MEMBER_ROLE $DEMO_TENANT 2>&1 >/dev/null
    keystone add-user-role $DEMO_USER $SYSADMIN_ROLE $DEMO_TENANT 2>&1 >/dev/null
    keystone add-user-role $DEMO_USER $NETADMIN_ROLE $DEMO_TENANT 2>&1 >/dev/null
    keystone add-user-role $DEMO_USER $MEMBER_ROLE $INVIS_TENANT 2>&1 >/dev/null
    keystone add-user-role $ADMIN_USER $ADMIN_ROLE $DEMO_TENANT 2>&1 >/dev/null

    # TODO(termie): these two might be dubious
    keystone add-user-role $ADMIN_USER $KEYSTONEADMIN_ROLE $ADMIN_TENANT 2>&1 >/dev/null
    keystone add-user-role $ADMIN_USER $KEYSTONESERVICE_ROLE $ADMIN_TENANT 2>&1 >/dev/null
    ###
fi

# Services
keystone service-create \
                                 --name=nova \
                                 --type=compute \
                                 --description="Nova Compute Service" 2>&1 >/dev/null

keystone service-create \
                                 --name=ec2 \
                                 --type=ec2 \
                                 --description="EC2 Compatibility Layer" 2>&1 >/dev/null

keystone service-create \
                                 --name=glance \
                                 --type=image \
                                 --description="Glance Image Service" 2>&1 >/dev/null

keystone service-create \
                                 --name=keystone \
                                 --type=identity \
                                 --description="Keystone Identity Service" 2>&1 >/dev/null


if [[ "$ENABLED_SERVICES" =~ "n-vol" ]]; then
    keystone service-create \
                                 --name="nova-volume" \
                                 --type=volume \
                                 --description="Nova Volume Service" 2>&1 >/dev/null
fi

if [[ "$ENABLED_SERVICES" =~ "swift" ]]; then
    keystone service-create \
                                 --name=swift \
                                 --type="object-store" \
                                 --description="Swift Service" 2>&1 >/dev/null
fi
if [[ "$ENABLED_SERVICES" =~ "quantum-server" ]]; then
    keystone service-create \
                                 --name=quantum \
                                 --type=network \
                                 --description="Quantum Service" 2>&1 >/dev/null
fi
                                 
                                 
# create ec2 creds and parse the secret and access key returned
if [[ -n "$KEYSTONE_COMMAND_4375" ]]; then
    RESULT=`keystone ec2-credentials-create --tenant_id=$ADMIN_TENANT --user=$ADMIN_USER`
else
    RESULT=`keystone ec2-create-credentials --tenant_id=$ADMIN_TENANT --user_id=$ADMIN_USER`
fi
    echo `$@ | grep id | awk '{print $4}'`
ADMIN_ACCESS=`echo "$RESULT" | grep access | awk '{print $4}'`
ADMIN_SECRET=`echo "$RESULT" | grep secret | awk '{print $4}'`


if [[ -n "$KEYSTONE_COMMAND_4375" ]]; then
    RESULT=`keystone ec2-credentials-create --tenant_id=$DEMO_TENANT --user=$DEMO_USER`
else
    RESULT=`keystone ec2-create-credentials --tenant_id=$DEMO_TENANT --user_id=$DEMO_USER`
fi
DEMO_ACCESS=`echo "$RESULT" | grep access | awk '{print $4}'`
DEMO_SECRET=`echo "$RESULT" | grep secret | awk '{print $4}'`

# Added! (NOT IN ORIGINAL)
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

