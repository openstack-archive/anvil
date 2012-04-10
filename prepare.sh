#!/bin/bash

if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root!" 1>&2
   exit 1
fi

# This should follow what is on the following website.
ME=`basename $0`

if [[ `cat /etc/issue | grep -i "ubuntu"` ]] ; then
    PKGS="gcc git pep8 pylint python python-dev python-iniparse python-pip python-progressbar python-yaml"
    PIPS="netifaces termcolor"
    APT="apt-get -y -qq"
    PIP="pip -q"
    # Now do it!
    echo "Preparing DEVSTACKpy for ubuntu."
    echo "Installing packages: $PKGS"
    $APT install $PKGS
    echo "Installing pypi packages: $PIPS"
    $PIP install netifaces termcolor --upgrade
elif [[ `cat /etc/issue | grep -i "red hat enterprise.*release.*6.*"` ]] ; then
    EPEL_RPM="epel-release-6-5.noarch.rpm"
    PKGS="gcc git pylint python python-netifaces python-pep8 python-pip python-progressbar PyYAML"
    PIPS="termcolor iniparse==0.4"
    PIP="pip-python -q"
    YUM="yum install -q -y"
    WGET="wget -q"
    # Now do it!
    echo "Preparing DEVSTACKpy for RHEL 6"
    echo "Fetching and installing EPEL rpm: $EPEL_RPM"
    TMP_DIR=`mktemp -d`
    $WGET http://download.fedoraproject.org/pub/epel/6/i386/$EPEL_RPM -O $TMP_DIR/$EPEL_RPM
    $YUM install $TMP_DIR/$EPEL_RPM
    rm -rf $TMP_DIR
    echo "Installing packages: $PKGS"
    $YUM install $PKGS
    echo "Installing pypi packages: $PIPS"
    $PIP install $PIPS --upgrade
elif [[ `cat /etc/issue | grep -i "fedora.*release.*16"` ]] ; then
    PKGS="gcc git pylint python python-netifaces python-pep8 python-pip python-progressbar PyYAML python-iniparse"
    PIPS="termcolor"
    PIP="pip-python -q"
    YUM="yum install -q -y"
    # Now do it!
    echo "Preparing DEVSTACKpy for Fedora 16"
    echo "Installing packages: $PKGS"
    $YUM install $PKGS
    echo "Installing pypi packages: $PIPS"
    $PIP install $PIPS --upgrade
else
    echo "DEVSTACKpy '$ME' is being ran on an unknown distribution."
fi


