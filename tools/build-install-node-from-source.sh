#!/bin/bash
set -x

nodejs_dir="`pwd`/.nodejs-build-dir"
mkdir $nodejs_dir
cd $nodejs_dir

echo "Downloading http://nodejs.org/dist/node-latest.tar.gz"
wget "http://nodejs.org/dist/node-latest.tar.gz"
tar -xzf node-latest.tar.gz

VERSION=`ls $nodejs_dir/ | grep node-v | cut -d 'v' -f2`
echo $VERSION

cd node-v$VERSION*
export CFLAGS=" -w -pipe -O3"
export CXXFLAGS=" -w -pipe -O3"
./configure --prefix=/usr

echo
echo "Building Node ..."
make

echo
echo "Installing into $nodejs_dir/install-root ..."
mkdir -p "$nodejs_dir/install-root"
make install DESTDIR="$nodejs_dir/install-root"

cd $nodejs_dir
echo
echo "Building RPM ..."
mkdir -p "$nodejs_dir/RPMS"

RELEASE=1
echo "Name:     nodejs

Version:  $VERSION
Release:  $RELEASE
Summary:  Server Side JavaScript Engine	
URL:      http://nodejs.org	
Group:    Development/Languages	
License:  MIT and BSD
Requires: openssl, zlib, glibc

%description
Node.js is Google V8 JavaScript with an evented I/O based interface to POSIX.  This RPM was built using https://github.com/ddopson/nodejs-rpm-builder
as a reference

%files
%defattr(-,root,root,-)
/" > package.spec

rpmbuild -bb package.spec --buildroot "$nodejs_dir/install-root" --define "_topdir $nodejs_dir" --define "VERSION $VERSION"

yum install -y -q $nodejs_dir/RPMS/x86_64/nodejs-$VERSION-$RELEASE.x86_64.rpm

rm -rf $nodejs_dir
