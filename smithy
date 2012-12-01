#!/bin/bash

if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root!" 1>&2
   exit 1
fi

shopt -s nocasematch

RHEL_VERSION=$(lsb_release  -r  | awk '{ print $2 }' | cut -d"." -f1)
EPEL_RPM_LIST="http://mirrors.kernel.org/fedora-epel/$RHEL_VERSION/i386"
NODE_RPM_URL="http://nodejs.tchol.org/repocfg/el/nodejs-stable-release.noarch.rpm"
PKG_DEPS=$(cat "tools/pkg-requires" | egrep -v "^\s*(#|$)")
PIP_DEP_FN="tools/pip-requires"
YUM_OPTS="--assumeyes --nogpgcheck"
PIP_CMD="pip-python"

# Source in our variables (or overrides)
source ".anvilrc"
if [ -n "$SUDO_USER" ]; then
    USER_HOME=$(getent passwd $SUDO_USER | cut -d: -f6)
    if [ -n "$USER_HOME" ]; then
        HOME_RC="${USER_HOME}/.anvilrc"
        if [ -f "$HOME_RC" ]; then
            source "$HOME_RC"
        fi
    fi
fi

ARGS="$@"
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

bootstrap_node()
{
    if [ -z "$NODE_RPM_URL" ]; then
        return 0
    fi
    echo "Installing node.js yum repository configuration."
    JS_REPO_RPM_FN=$(basename $NODE_RPM_URL)
    if [ ! -f "/tmp/$JS_REPO_RPM_FN" ]; then
        echo "Downloading $JS_REPO_RPM_FN to /tmp/$JS_REPO_RPM_FN..."
        wget -q -O "/tmp/$JS_REPO_RPM_FN" "$NODE_RPM_URL"
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi
    echo "Installing /tmp/$JS_REPO_RPM_FN..."
    yum install $YUM_OPTS -t "/tmp/$JS_REPO_RPM_FN" 2>&1
}

bootstrap_epel()
{
    if [ -z "$EPEL_RPM_LIST" ]; then
        return 0
    fi
    echo "Locating the EPEL rpm..."
    if [ -z "$EPEL_RPM" ]; then
        EPEL_RPM=$(curl -s "$EPEL_RPM_LIST/" | grep -io ">\s*epel.*.rpm\s*<" | grep -io "epel.*.rpm")
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi
    if [ ! -f "/tmp/$EPEL_RPM" ]; then
        echo "Downloading $EPEL_RPM to /tmp/$EPEL_RPM"
        wget -q -O "/tmp/$EPEL_RPM" "$EPEL_RPM_LIST/$EPEL_RPM"
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi
    echo "Installing /tmp/$EPEL_RPM..."
    yum install $YUM_OPTS -t "/tmp/$EPEL_RPM" 2>&1
}

has_bootstrapped()
{
    checksums=$(get_checksums)
    for i in $BOOT_FILES; do
        if [ -f $i ]; then
            contents=`cat $i`
            if [ "$contents" == "$checksums" ]; then
                return 0
            fi
        fi
    done
    return 1
}

get_checksums()
{
    pkg_checksum=$(md5sum tools/pkg-requires)
    pip_checksum=$(md5sum tools/pip-requires)
    echo "$pkg_checksum"
    echo "$pip_checksum"
}

bootstrap_rhel()
{
    echo "Bootstrapping RHEL: $1"
    echo "Please wait..."
    bootstrap_node
    bootstrap_epel
    if [ -n "$PKG_DEPS" ]; then
        echo "Installing distribution dependencies..."
        yum install $YUM_OPTS $PKG_DEPS 2>&1
    fi
    if [ -f "$PIP_DEP_FN" ]; then
        echo "Installing pypi dependencies..."
        $PIP_CMD install -U -I -r "$PIP_DEP_FN"
    fi
    return 0
}

run_smithy()
{
    PYTHON=`which python`
    exec $PYTHON anvil $ARGS
}

puke()
{
    # TODO(harlowja) better way to do this??
    cleaned_force=$(python -c "f='$FORCE'; print(f.lower().strip())")
    if [[ "$cleaned_force" == "yes" ]]; then
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
    bootstrap_rhel $RH_VER
    if [ $? -eq 0 ]; then
        # Write the checksums of the requirement files
        # which if new requirements are added will cause new checksums
        # and a new dependency install...
        checksums=$(get_checksums)
        for i in $BOOT_FILES; do
            echo -e "$checksums" > $i
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



