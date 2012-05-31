#!/bin/bash

if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root!" 1>&2
   exit 1
fi

set -x

# Now do it!
echo "Preparing ANVIL for Fedora"

# Install the needed yum packages
PKGS="gcc git pylint python python-netifaces python-pep8 python-pip python-progressbar PyYAML python-iniparse"
echo "Installing packages: $PKGS"
yum -q -y install $PKGS

# Install the needed pypi packages
PIPS="termcolor"
echo "Installing pypi packages: $PIPS"
pip-python -q install $PIPS --upgrade
