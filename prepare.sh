#!/bin/bash

if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root!" 1>&2
   exit 1
fi

# This should follow what is on the following website.
URL="https://github.com/yahoo/Openstack-DevstackPy/wiki/Simple-Setup"
ME=`basename $0`

if [[ `cat /etc/issue | grep -i "ubuntu"` ]] ; then
    PKGS="git python-pip python-dev python-yaml gcc pep8 pylint python-progressbar python"
    PIPS="netifaces termcolor"
    APT="apt-get -y -qq"
    PIP="pip -q"
    # Now do it!
    echo "Preparing DEVSTACKpy for ubuntu."
    echo "Installing packages: $PKGS"
    $APT install $PKGS
    echo "Installing pypi packages: $PIPS"
    $PIP install netifaces termcolor
    echo "DEVSTACKpy for ubuntu is ready to rock & roll."
elif [[ `cat /etc/issue | grep -i "red hat.*release.*6.*"` ]] ; then
    EPEL_RPM="epel-release-6-5.noarch.rpm"
    PKGS="python-pip gcc python-netifaces git python-pep8 pylint python-progressbar python"
    PIPS="termcolor pyyaml"
    PIP="pip-python -q"
    YUM="yum install -q"
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
    $PIP install $PIPS
    echo "DEVSTACKpy for RHEL 6 is ready to rock & roll."
elif [[ `cat /etc/issue | grep -i "fedora.*release.*16"` ]] ; then
    PKGS="python-pip gcc python-netifaces git python-pep8 pylint python-yaml python python-progressbar"
    PIPS="termcolor"
    PIP="pip-python -q"
    YUM="yum install -q"
    # Now do it!
    echo "Preparing DEVSTACKpy for Fedora 16"
    echo "Installing packages: $PKGS"
    $YUM install $PKGS
    echo "Installing pypi packages: $PIPS"
    $PIP install $PIPS
    echo "DEVSTACKpy for Fedora 16 is ready to rock & roll."
else
    echo "DEVSTACKpy '$ME' is being ran on an unknown distrobution."
    echo "Please update '$URL' when you get it to run. Much appreciated!"
fi


