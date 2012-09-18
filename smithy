#!/bin/bash

if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root!" 1>&2
   exit 1
fi

shopt -s nocasematch

ARGS="$@"
VER=$(python -c "from anvil import version; print version.version_string()")
PWD=`pwd`
if [ -z "$BOOT_FILES" ]; then
    BOOT_FN=".anvil_bootstrapped"
    BOOT_FILES="${PWD}/$BOOT_FN"
    if [ -n "$SUDO_USER" ]; then
        USER_HOME=$(getent passwd $SUDO_USER | cut -d: -f6)
        if [ -n "$USER_HOME" ]; then
            BOOT_FILES="${BOOT_FILES} ${USER_HOME}/$BOOT_FN"
        fi
    fi
    BOOT_FILES="${BOOT_FILES} ${HOME}/$BOOT_FN"
fi

has_bootstrapped()
{
    for i in $BOOT_FILES; do
        if [ -f $i ]; then
            contents=`cat $i`
            if [ "$contents" == "$VER" ]; then
                return 0
            fi
        fi
    done
    return 1
}

bootstrap_rh()
{
    echo "Bootstrapping RHEL: $1"
    echo "Please wait..."

    echo "Installing node.js yum repository configuration."
    JS_REPO_RPM_FN="nodejs-stable-release.noarch.rpm"
    if [ ! -f "/tmp/$JS_REPO_RPM_FN" ]; then
        echo "Downloading $JS_REPO_RPM_FN"
        wget -q -O "/tmp/$JS_REPO_RPM_FN" "http://nodejs.tchol.org/repocfg/el/$JS_REPO_RPM_FN"
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi
    echo "Installing /tmp/$JS_REPO_RPM_FN."
    yum install --assumeyes --nogpgcheck -t "/tmp/$JS_REPO_RPM_FN" 2>&1

    echo "Locating the EPEL rpm."
    EPEL_RPM=$(curl -s "http://mirrors.kernel.org/fedora-epel/6/i386/" | grep -io ">\s*epel.*.rpm\s*<" | grep -io "epel.*.rpm")
    if [ $? -ne 0 ]; then
        return 1
    fi
    if [ ! -f "/tmp/$EPEL_RPM" ]; then
        echo "Downloading $EPEL_RPM."
        wget -q -O "/tmp/$EPEL_RPM" "http://mirrors.kernel.org/fedora-epel/6/i386/$EPEL_RPM"
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi
    echo "Installing /tmp/$EPEL_RPM."
    yum install --assumeyes --nogpgcheck -t "/tmp/$EPEL_RPM" 2>&1

    echo "Installing needed distribution dependencies:"
    pkgs="gcc git pylint python python-netifaces python-pep8 python-cheetah"
    pkgs="$pkgs python-pip python-progressbar PyYAML python-ordereddict python-iso8601"
    yum install -y $pkgs 2>&1

    echo "Installing needed pypi dependencies:"
    pip-python install -U -I termcolor iniparse "keyring==0.9.2"
    return 0
}

run_smithy()
{
    PYTHON=`which python`
    exec $PYTHON anvil $ARGS
}

puke()
{
    if [[ "$FORCE" == "yes" ]]; then
        run_smithy
    else
        echo "To run anyway set FORCE=yes and rerun."
        exit 1
    fi
}

has_bootstrapped
if [ $? -eq 0 ]; then
    run_smithy
fi

TYPE=$(lsb_release -d | cut  -f 2)
if [[ "$TYPE" =~ "Red Hat Enterprise Linux Server" ]]; then
    RH_VER=$(lsb_release -r | cut  -f 2)
    BC_OK=$(echo "$RH_VER < 6" | bc)
    if [ "$BC_OK" == "1" ]; then
        echo "This script must be ran on RHEL 6.0+ and not RHEL $RH_VER."
        puke
    fi
    bootstrap_rh $RH_VER
    if [ $? -eq 0 ]; then
        for i in $BOOT_FILES; do
            echo "$VER" > $i
        done
        run_smithy
    else
        echo "Bootstrapping RHEL $RH_VER failed."
        exit 1
    fi
else
    echo "Anvil has not been tested on distribution '$TYPE'"
    puke
fi



