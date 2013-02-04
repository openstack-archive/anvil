#!/bin/bash

shopt -s nocasematch

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

PWD=`pwd`
if [ -z "$BOOT_FILES" ]; then
    BOOT_FN=".anvil_bootstrapped"
    BOOT_FILES="${PWD}/$BOOT_FN"
fi

cache_and_install_rpm_url()
{
    url=${1:?"Error: rpm uri is undefined!"}
    cachedir=${RPM_CACHEDIR:-'/tmp'}
    rpm=$(basename $url)
    if [ ! -f "$cachedir/$rpm" ]; then
	echo "Downloading $rpm to $cachedir..."
        curl -s $url -o "$cachedir/$rpm" || return 1
    fi
    install_rpm "$cachedir/$rpm"
    return $?
}

install_rpm()
{
    rpmstr=${1:?"Error: rpm to install is undefined!"}
    rpm=$rpmstr
    [ $(dirname $rpm) = '.' ] || rpm=$(rpm -qp $rpmstr 2> /dev/null )
    rpm -q $rpm > /dev/null 2>&1 && return 0
    echo "Installing rpm requirement '$rpm'"
    yum install $YUM_OPTS "$rpmstr" 2>&1
    return $?
}

install_pypi()
{
    pypi=${1:?"Error: pypi to install is undefined!"}
    # TODO: Figure out a way to make pypi installation idempotent -- 
    # in the simple case we can simply return true if the package
    # appears in the output of 'pip freeze' but this doesn't handle
    # the 'pkg>=1.0' syntax. -I explicitly reinstalls.
    $PIP_CMD install -U -I $pypi
    return $?
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
	format=$(echo $pkg | cut -d: -f1)
        name=$(echo $pkg | cut -d: -f2)
        echo "Installing $format requirement '$name'"
        install_$format $name
	if [ $? != 0 ]; then
            echo "Error: Installation of $format package '$name' failed!"
	    return $?
	fi
    done
}

require()
{
    format=${1?"Error: Specify a format as the first arg to require!"}
    name=${2?"Error: No name specified for required $format"}
    case "$format" in
        rpm|pypi)
            PACKAGES="$PACKAGES $format:$name"
        ;;
        *)
            echo "Error: Smithy does not know how to handle $format requirements!"
            exit 1
        ;;
    esac
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
    echo "Running 'sudo smithy --bootstrap' will attempt to do so." >&2
    exit 1
fi

## Bootstrap smithy
if [ "$(id -u)" != "0" ]; then
    echo "You must run 'smithy --bootstrap' with root privileges!" >&2
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
