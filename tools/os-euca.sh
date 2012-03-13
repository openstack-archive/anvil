#!/usr/bin/env bash

# From devstack.sh commit 0bd2410d469f11934b5965d83b57d56418e66b48

# Create EC2 credentials for the current user as defined by OS_TENANT_NAME:OS_USERNAME

set -x

if [[ -n "$1" ]]; then
    USERNAME=$1
fi

if [[ -n "$2" ]]; then
    TENANT=$2
fi

# Find the other rc files
RC_DIR=../
CORE_RC="os-core.rc"

# Get user configuration
source $RC_DIR/$CORE_RC

# Set the ec2 url so euca2ools works
export EC2_URL=$(keystone catalog --service ec2 | awk '/ publicURL / { print $4 }')

# Create EC2 credentials for the current user
CREDS=$(keystone ec2-credentials-create)
export EC2_ACCESS_KEY=$(echo "$CREDS" | awk '/ access / { print $4 }')
export EC2_SECRET_KEY=$(echo "$CREDS" | awk '/ secret / { print $4 }')

# Euca2ools Certificate stuff for uploading bundles
NOVA_KEY_DIR=${NOVA_KEY_DIR:-$RC_DIR}
export S3_URL=$(keystone catalog --service s3 | awk '/ publicURL / { print $4 }')
export EC2_USER_ID=42 # nova does not use user id, but bundling requires it
export EC2_PRIVATE_KEY=${NOVA_KEY_DIR}/pk.pem
export EC2_CERT=${NOVA_KEY_DIR}/cert.pem
export NOVA_CERT=${NOVA_KEY_DIR}/cacert.pem
export EUCALYPTUS_CERT=${NOVA_CERT} # euca-bundle-image seems to require this set
alias ec2-bundle-image="ec2-bundle-image --cert ${EC2_CERT} --privatekey ${EC2_PRIVATE_KEY} --user ${EC2_USER_ID} --ec2cert ${NOVA_CERT}"
alias ec2-upload-bundle="ec2-upload-bundle -a ${EC2_ACCESS_KEY} -s ${EC2_SECRET_KEY} --url ${S3_URL} --ec2cert ${NOVA_CERT}"

