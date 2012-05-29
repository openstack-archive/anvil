#!/bin/bash

if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root!" 1>&2
   exit 1
fi

set -x

# Now do it!
echo "Preparing ANVIL for ubuntu."

# Install the needed apt packages
PKGS="gcc git pep8 pylint python python-dev python-iniparse python-pip python-progressbar python-yaml"
echo "Installing packages: $PKGS"
apt-get -y -qq install $PKGS

# Install the needed pypi packages
PIPS="netifaces termcolor"
echo "Installing pypi packages: $PIPS"
pip -q install netifaces termcolor --upgrade
