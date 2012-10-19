#!/usr/bin/env bash

# From devstack.sh commit 0bd2410d469f11934b5965d83b57d56418e66b48

# Create EC2 credentials for the current user as defined by OS_TENANT_NAME:OS_USERNAME

ME=`basename $0`

if [[ -n "$1" ]]; then
    USERNAME=$1
fi

if [[ -n "$2" ]]; then
    TENANT=$2
fi

# Find the other rc files
RC_DIR="/etc/anvil"
CORE_RC="install.rc"
EC2_RC="euca.rc"

if [ ! -f "$RC_DIR/$CORE_RC" ];
then
    GEN_CMD="smithy -a install"
    echo "File '$RC_DIR/$CORE_RC' needed before running '$ME'"
    echo "Please run './$GEN_CMD' to get this file."
    exit 1
fi

# Get user configuration
source $RC_DIR/$CORE_RC

# Woah!
if [ -f $RC_DIR/$EC2_RC ];
then
    echo "Woah cowboy you seem to already have '$RC_DIR/$EC2_RC'!"
    while true; do
        read -p "Overwrite it and continue? " yn
        case $yn in
            [Yy]* ) break;;
            [Nn]* ) exit 1;;
            * ) echo "Please answer y or n.";;
        esac
    done
fi

# Bug https://bugs.launchpad.net/keystone/+bug/962600
unset SERVICE_TOKEN
unset SERVICE_ENDPOINT

# Now we start showing whats happening
set -x

# Set the ec2 url so euca2ools works
EC2_URL=$(keystone catalog --service ec2 | awk '/ publicURL / { print $4 }')

# Create EC2 credentials for the current user
CREDS=$(keystone ec2-credentials-create)
EC2_ACCESS_KEY=$(echo "$CREDS" | awk '/ access / { print $4 }')
EC2_SECRET_KEY=$(echo "$CREDS" | awk '/ secret / { print $4 }')

# Euca2ools Certificate stuff for uploading bundles
NOVA_KEY_DIR=${NOVA_KEY_DIR:-$RC_DIR}
S3_URL=$(keystone catalog --service s3 | awk '/ publicURL / { print $4 }')

# ??
EC2_USER_ID=42

# For a comment
NOW=`date`

# Make a nice file for u
ENV_FN=$RC_DIR/$EC2_RC
echo "Making $ENV_FN"

cat > $ENV_FN <<EOF
# Created on $NOW

# General goodies
export EC2_ACCESS_KEY=$EC2_ACCESS_KEY
export EC2_SECRET_KEY=$EC2_SECRET_KEY
export NOVA_KEY_DIR=$NOVA_KEY_DIR
export EC2_URL=$EC2_URL
export S3_URL=$S3_URL
export EC2_USER_ID=$EC2_USER_ID

export NOVA_CERT=\${NOVA_KEY_DIR}/cacert.pem
export EC2_CERT=\${NOVA_KEY_DIR}/cert.pem
export EC2_PRIVATE_KEY=\${NOVA_KEY_DIR}/pk.pem
export EUCALYPTUS_CERT=\${NOVA_CERT} # euca-bundle-image seems to require this set

# Aliases
alias ec2-bundle-image="ec2-bundle-image --cert \${EC2_CERT} --privatekey \${EC2_PRIVATE_KEY} --user \${EC2_USER_ID} --ec2cert \${NOVA_CERT}"
alias ec2-upload-bundle="ec2-upload-bundle -a \${EC2_ACCESS_KEY} -s \${EC2_SECRET_KEY} --url \${S3_URL} --ec2cert \${NOVA_CERT}"
EOF

