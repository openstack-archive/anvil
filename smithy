#!/bin/bash

if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root!" 1>&2
   exit 1
fi

shopt -s nocasematch

RHEL_VERSION=$(lsb_release  -r  | awk '{ print $2 }' | cut -d"." -f1)
EPEL_RPM_LIST="http://mirrors.kernel.org/fedora-epel/$RHEL_VERSION/i386"
NODE_RPM_URL="http://nodejs.tchol.org/repocfg/el/nodejs-stable-release.noarch.rpm"
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
    return $?
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
    return $?
}

clean_requires()
{
    # First remove comments and blank lines from said files
    if [ -f "tools/pkg-requires" ]; then
        grep -Pv "(^\s*#.*$|^\s*$)" tools/pkg-requires > /tmp/anvil-pkg-requires
    else
        echo "" > /tmp/anvil-pkg-requires
    fi
    if [ -f "tools/pip-requires" ]; then
        grep -Pv "(^\s*#.*$|^\s*$)" tools/pip-requires > /tmp/anvil-pip-requires
    else
        echo "" > /tmp/anvil-pip-requires
    fi
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
    # Now checksum said files to be used in telling if said files have changed
    pkg_checksum=$(md5sum /tmp/anvil-pkg-requires)
    pip_checksum=$(md5sum /tmp/anvil-pip-requires)
    echo "$pkg_checksum"
    echo "$pip_checksum"
}

bootstrap_rhel()
{
    echo "Bootstrapping RHEL: $1"
    echo "Please wait..."

    # Node is typically needed for horizon (some css stuff)
    bootstrap_node
    if [ "$?" != "0" ];
    then
        return $?
    fi

    # EPEL provides most of the python dependencies for RHEL
    bootstrap_epel
    if [ "$?" != "0" ];
    then
        return $?
    fi

    # Install line by line since yum and pip
    # work better when installed individually (error reporting
    # and interdependency wise).
    for line in `cat /tmp/anvil-pkg-requires`; do
        echo "Install pkg requirement $line"
        yum install $YUM_OPTS $line 2>&1 > /dev/null
        if [ "$?" != "0" ];
        then
            echo "Failed installing ${line}!!"
            return 1
        fi
    done
    for line in `cat /tmp/anvil-pip-requires`; do
        echo "Install pip requirement $line"
        $PIP_CMD install -U -I $line 2>&1 > /dev/null
        if [ "$?" != "0" ];
        then
            echo "Failed installing ${line}!!"
            return 1
        fi
    done
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

clean_requires
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



