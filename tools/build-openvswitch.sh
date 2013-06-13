#!/bin/bash

# This is a sample script to build OpenVSwitch for
# development needs. It is based on
# http://n40lab.wordpress.com/2013/06/03/centos-6-4-openvswitch-installation/

set -ex

VERSION=1.10.0

sudo yum -y install wget openssl-devel
sudo yum -y groupinstall "Development Tools"

rm -f ~/rpmbuild/RPMS/*/{kmod-openvswitch,openvswitch}*

cd $(mktemp -d)
wget http://openvswitch.org/releases/openvswitch-${VERSION}.tar.gz
tar xfz openvswitch-${VERSION}.tar.gz
cd openvswitch-${VERSION}
mkdir -p ~/rpmbuild/SOURCES
cp ../openvswitch-${VERSION}.tar.gz rhel/openvswitch-kmod.files ~/rpmbuild/SOURCES/
rpmbuild -bb rhel/openvswitch.spec
rpmbuild -bb rhel/openvswitch-kmod-rhel6.spec

sudo yum -y install ~/rpmbuild/RPMS/*/{kmod-openvswitch,openvswitch}-${VERSION}*.rpm
