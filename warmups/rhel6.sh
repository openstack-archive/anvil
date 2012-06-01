#!/bin/bash

if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root!" 1>&2
   exit 1
fi

set -x

# Figure out the epel rpm, as it seems to change alot...
# Just use the following epel http mirror
EPEL_RPM=$(curl -s "http://epel.mirror.freedomvoice.com/6/i386/" | \
           grep -Pi "(epel-release(.*).rpm)" | perl -ne 'm/(epel.*?rpm)/; print "$1";')
if [ -z "$EPEL_RPM" ]; then
    echo "Sorry no epel rpm found!"
    exit 1
fi

# Now do it!
echo "Preparing ANVIL for RHEL 6"
URI="http://epel.mirror.freedomvoice.com/6/i386/$EPEL_RPM"
echo "Fetching epel rpm: $EPEL_RPM from $URI"
TMP_DIR=`mktemp -d`
wget -q $URI -O $TMP_DIR/$EPEL_RPM
if [ "$?" -ne "0" ]; then
    echo "Sorry, stopping since download from $URI failed."
    exit 1
fi

echo "Installing $TMP_DIR/$EPEL_RPM"
OUT=$(yum -y -q install $TMP_DIR/$EPEL_RPM 2>&1)
OUT_EXITCODE=$?
if [[ "$OUT" =~ "Nothing to do" ]]
then
    echo "It appears $EPEL_RPM is already installed."
elif [[ "$OUT" =~ "Already installed" ]]
then
    echo "Installed!"
elif [ "$OUT_EXITCODE" -ne "0" ]
then
    echo "Sorry, stopping since install of $TMP_DIR/$EPEL_RPM failed."
    exit 1
fi

# Install the needed yum packages
PKGS="gcc git pylint python python-netifaces python-pep8 python-pip python-progressbar PyYAML python-ordereddict"
echo "Installing packages: $PKGS"
yum -y -q install $PKGS

# Install the needed pypi packages
PIPS="termcolor iniparse"
echo "Installing pypi packages: $PIPS"
pip-python -q install $PIPS --upgrade

exit 0
