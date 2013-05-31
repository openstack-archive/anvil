#!/bin/bash

shopt -s nocasematch

SMITHY_NAME=$(readlink -f "$0")
cd "$(dirname "$0")"

YUM_OPTS="--assumeyes --nogpgcheck"
PIP_CMD=""
PY2RPM_CMD="$PWD/tools/py2rpm"

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

if [ -z "$BOOT_FILES" ]; then
    BOOT_FN=".anvil_bootstrapped"
    BOOT_FILES="${PWD}/$BOOT_FN"
fi

conflicts() {
    echo "Removing conflicting packages $(echo $@)"
    yum erase -y $@
}

find_pip()
{
    if [ -n "$PIP_CMD" ]; then
        return
    fi
    PIP_CMD=""
    for name in pip pip-python; do
        if which "$name" &>/dev/null; then
            PIP_CMD=$name
            break
        fi
    done
    if [ -z "$PIP_CMD" ]; then
        echo "pip or pip-python not found"
        exit 1
    fi
}

rpm_is_installed()
{
    local name="$(basename "$1")"
    rpm -q "${name%.rpm}" &>/dev/null
}

cache_and_install_rpm_url()
{
    url=${1:?"Error: rpm uri is undefined!"}
    cachedir=${RPM_CACHEDIR:-'/tmp'}
    rpm=$(basename $url)
    if rpm_is_installed "$rpm"; then
        return
    fi
    if [ ! -f "$cachedir/$rpm" ]; then
	echo "Downloading $rpm to $cachedir..."
        curl -s $url -o "$cachedir/$rpm" || return 1
    fi
    install_rpm "$cachedir/$rpm"
    return $?
}

install_rpm()
{
    local rpm_path=$1
    local py_name=$2

    if [ -n "$rpm_path" ]; then
        # install or update package
        yum install $YUM_OPTS "$rpm_path" && return 0
    fi
    if [ -z "$py_name" ]; then
        return 1
    fi
    # RPM is not available. Try to build it on fly
    pip_tmp_dir=$(mktemp -d)
    find_pip
    $PIP_CMD install -U -I $py_name --download "$pip_tmp_dir"
    echo "Building RPM for $py_name"
    rpm_names=$("$PY2RPM_CMD" "$pip_tmp_dir/"* 2>/dev/null |
        awk '/^Wrote: /{ print $2 }' | grep -v '.src.rpm' | sort -u)
    rm -rf "$pip_tmp_dir"
    if [ -z "$rpm_names" ]; then
        echo "No binary RPM was built for $py_name"
        return 1
    fi
    yum install $YUM_OPTS $rpm_names
}

bootstrap_epel()
{
    [ -z "$EPEL_RPM_URL" ] && return 0
    cache_and_install_rpm_url $EPEL_RPM_URL
    return $?
}

bootstrap_packages()
{
    [ -z "$PACKAGES" ] && return 0
    for pkg in $PACKAGES; do
	local rpm_name=$(echo $pkg | cut -d: -f1)
        local py_name=$(echo $pkg | cut -d: -f2)
        install_rpm $rpm_name $py_name
        install_status=$?
	if [ "$install_status" != 0 ]; then
            echo "Error: Installation of package '$rpm_name' failed!"
	    return "$install_status"
	fi
    done
}

require()
{
    local rpm_name=$1
    local py_name=$2
    if [ -z "$rpm_name" -a -z "$py_name" ]; then
        echo "Please specify at RPM or Python package name"
        exit 1
    fi
    PACKAGES="$PACKAGES $rpm_name:$py_name"
}

needs_bootstrap()
{
    $BOOTSTRAP && return 0 
    checksums=$(get_checksums)
    for i in $BOOT_FILES; do
        if [ -f $i ]; then
            contents=`cat $i`
            [ "$contents" = "$checksums" ] && return 1
        fi
    done
    return 0
}

get_checksums()
{
    # used to tell if the file have changed
    echo $(md5sum "$BSCONF_FILE")
}

run_smithy()
{
    PYTHON=`which python`
    exec $PYTHON anvil $ARGS
}

puke()
{
    cleaned_force=$(echo $FORCE | sed -e 's/\([A-Z]\)/\L\1/g;s/\s//g')
    if [[ "$cleaned_force" == "yes" ]]; then
        run_smithy
    else
        echo "To run anyway set FORCE=yes and rerun." >&2
        exit 1
    fi
}

## Identify which bootstrap configuration file to use: either set
## explicitly (BSCONF_FILE) or determined based on the os distribution:
BSCONF_DIR=${BSCONF_DIR:-$(dirname $(readlink -f "$0"))/tools/bootstrap}
get_os_info(){
    OS=`uname`
    if [ "${OS}" = "Linux" ] ; then
        if [ -f /etc/redhat-release ] ; then
            PKG="rpm"
            OSNAME=`cat /etc/redhat-release`
            OSDIST=`cat /etc/redhat-release | sed -e 's/release.*$//g;s/\s//g'`
            PSUEDONAME=`cat /etc/redhat-release | sed s/.*\(// | sed s/\)//`
            RELEASE=`cat /etc/redhat-release | sed s/.*release\ // | sed s/\ .*//`
        elif [ -f /etc/debian_version ] ; then
            PKG="deb"
            OSDIST=`cat /etc/lsb-release | grep '^DISTRIB_ID' | awk -F= '{ print $2 }'`
            PSUEDONAME=`cat /etc/lsb-release | grep '^DISTRIB_CODENAME' | awk -F= '{ print $2 }'`
            RELEASE=`cat /etc/lsb-release | grep '^DISTRIB_RELEASE' | awk -F= '{ print $2 }'`
            OSNAME="$OSDIST $RELEASE ($PSUEDONAME)"
        fi
    fi
}

get_os_info

if [ -z "$BSCONF_FILE" ]; then
    BSCONF_FILE="$BSCONF_DIR/$OSDIST"
fi

ARGS=""
BOOTSTRAP=false

# Ad-hoc getopt to handle long opts. 
#
# Smithy opts are consumed while those to anvil are copied through.
while [ ! -z $1 ]; do
    case "$1" in
        '--bootstrap')
	    BOOTSTRAP=true
	    shift
	    ;;
	'--force')
	    FORCE=yes
	    shift
	    ;;
	*)
	    ARGS="$ARGS $1"
	    shift
	    ;;
    esac
done

if ! needs_bootstrap; then
    run_smithy
elif ! $BOOTSTRAP; then
    echo "This system needs to be updated in order to run anvil!" >&2
    echo "Running 'sudo $SMITHY_NAME --bootstrap' will attempt to do so." >&2
    exit 1
fi

## Bootstrap smithy
if [ "$(id -u)" != "0" ]; then
    echo "You must run '$SMITHY_NAME --bootstrap' with root privileges!" >&2
    exit 1
fi
if [ ! -f $BSCONF_FILE ]; then 
    echo "Anvil has not been tested on distribution '$OSNAME'" >&2
    puke
fi

echo "Sourcing $BSCONF_FILE"
source $BSCONF_FILE
MIN_RELEASE=${MIN_RELEASE:?"Error: MIN_RELEASE is undefined!"}
SHORTNAME=${SHORTNAME:?"Error: SHORTNAME is undefined!"}

BC_OK=$(echo "$RELEASE < $MIN_RELEASE" | bc)
if [ "$BC_OK" == "1" ]; then
    echo "This script must be run on $SHORTNAME $MIN_RELEASE+ and not $SHORTNAME $RELEASE." >&2
    puke
fi

echo "Bootstrapping $SHORTNAME $RELEASE"
echo "Please wait..."
for step in ${STEPS:?"Error: STEPS is undefined!"}; do
    bootstrap_${step}
    if [ $? != 0 ]; then
        echo "Bootstrapping $SHORTNAME $RELEASE failed." >&2
        exit 1
    fi
done

# Write the checksums of the bootstrap file
# which if new requirements are added will cause new checksums
# and a new dependency install...
checksum=$(get_checksums)
for i in $BOOT_FILES; do
    echo -e $checksum > $i
done
echo "Success! Bootstrapped for $SHORTNAME $RELEASE"
exit 0
