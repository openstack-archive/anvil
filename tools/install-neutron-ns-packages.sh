#!/bin/bash

# This script is used to install 'kernel' and 'iproute'
# with network namespaces support for openstack-neutron
# from RDO havana repository.

set -e

echo "Adding RDO havana repo..."
sudo rpm -i --force http://rdo.fedorapeople.org/openstack-havana/rdo-release-havana.rpm
sudo yum clean all

echo "Installing 'kernel' and 'iproute' from RDO..."
sudo yum install -y kernel iproute

echo "Kernel updated. Please, reboot into it!"
