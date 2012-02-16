#!/bin/bash

# From devstack commit bd13b708f2 with some modifications

# These are used by keystone commands below (?)
export SERVICE_TOKEN=%SERVICE_TOKEN%
export SERVICE_ENDPOINT=$SERVICE_ENDPOINT

function get_id () {
    echo `$@ | grep id | awk '{print $4}'`
}

# Added! (NOT IN ORIGINAL)
ADMIN_USERNAME=%ADMIN_USERNAME%
ADMIN_PASSWORD=%ADMIN_PASSWORD%
DEMO_USER_NAME=%DEMO_USER_NAME%
INVIS_USER_NAME=invisible_to_admin
MEMBER_ROLE_NAME=Member
KEYSTONE_ADMIN_ROLE_NAME=KeystoneAdmin
KEYSTONE_SERVICE_ADMIN_ROLE_NAME=KeystoneServiceAdmin
SYSADMIN_ROLE_NAME=sysadmin
NETADMIN_ROLE_NAME=netadmin

# Tenants
ADMIN_TENANT=`get_id keystone tenant-create --name=$ADMIN_USERNAME`
DEMO_TENANT=`get_id keystone tenant-create --name=$DEMO_USER_NAME`
INVIS_TENANT=`get_id keystone tenant-create --name=$INVIS_USER_NAME`

# Users
ADMIN_USER=`get_id keystone user-create \
                                 --name=$ADMIN_USERNAME \
                                 --pass="$ADMIN_PASSWORD" \
                                 --email=admin@example.com`

DEMO_USER=`get_id keystone user-create \
                                 --name=$DEMO_USER_NAME \
                                 --pass="$ADMIN_PASSWORD" \
                                 --email=admin@example.com`

# Roles
ADMIN_ROLE=`get_id keystone role-create --name=$ADMIN_USERNAME`
MEMBER_ROLE=`get_id keystone role-create --name=$MEMBER_ROLE_NAME`
KEYSTONEADMIN_ROLE=`get_id keystone role-create --name=$KEYSTONE_ADMIN_ROLE_NAME`
KEYSTONESERVICE_ROLE=`get_id keystone role-create --name=$KEYSTONE_SERVICE_ADMIN_ROLE_NAME`
SYSADMIN_ROLE=`get_id keystone role-create --name=$SYSADMIN_ROLE_NAME`
NETADMIN_ROLE=`get_id keystone role-create --name=$NETADMIN_ROLE_NAME`


# Add Roles to Users in Tenants
keystone add-user-role $ADMIN_USER $ADMIN_ROLE $ADMIN_TENANT
keystone add-user-role $DEMO_USER $MEMBER_ROLE $DEMO_TENANT
keystone add-user-role $DEMO_USER $SYSADMIN_ROLE $DEMO_TENANT
keystone add-user-role $DEMO_USER $NETADMIN_ROLE $DEMO_TENANT
keystone add-user-role $DEMO_USER $MEMBER_ROLE $INVIS_TENANT
keystone add-user-role $ADMIN_USER $ADMIN_ROLE $DEMO_TENANT

# TODO(termie): these two might be dubious
keystone add-user-role $ADMIN_USER $KEYSTONEADMIN_ROLE $ADMIN_TENANT
keystone add-user-role $ADMIN_USER $KEYSTONESERVICE_ROLE $ADMIN_TENANT

# Services
keystone service-create \
                                 --name=nova \
                                 --type=compute \
                                 --description="Nova Compute Service"

keystone service-create \
                                 --name=ec2 \
                                 --type=ec2 \
                                 --description="EC2 Compatibility Layer"

keystone service-create \
                                 --name=glance \
                                 --type=image \
                                 --description="Glance Image Service"

keystone service-create \
                                 --name=keystone \
                                 --type=identity \
                                 --description="Keystone Identity Service"
if [[ "$ENABLED_SERVICES" =~ "swift" ]]; then
    keystone service-create \
                                 --name=swift \
                                 --type="object-store" \
                                 --description="Swift Service"
fi

# create ec2 creds and parse the secret and access key returned
RESULT=`keystone ec2-create-credentials --tenant_id=$ADMIN_TENANT --user_id=$ADMIN_USER`
    echo `$@ | grep id | awk '{print $4}'`
ADMIN_ACCESS=`echo "$RESULT" | grep access | awk '{print $4}'`
ADMIN_SECRET=`echo "$RESULT" | grep secret | awk '{print $4}'`

RESULT=`keystone ec2-create-credentials --tenant_id=$DEMO_TENANT --user_id=$DEMO_USER`
DEMO_ACCESS=`echo "$RESULT" | grep access | awk '{print $4}'`
DEMO_SECRET=`echo "$RESULT" | grep secret | awk '{print $4}'`

# write the secret and access to ec2rc to stderr for 
# pickup by devstack py! (CHANGED!)
cat 1>&2 <<EOF
ADMIN_ACCESS=$ADMIN_ACCESS
ADMIN_SECRET=$ADMIN_SECRET
DEMO_ACCESS=$DEMO_ACCESS
DEMO_SECRET=$DEMO_SECRET
EOF
