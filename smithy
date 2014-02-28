#!/bin/bash

locale -a | grep -q -e "^en_US$" && export LANG="en_US"

shopt -s nocasematch

SMITHY_NAME=$(readlink -f "$0")
cd "$(dirname "$0")"

VERBOSE="${VERBOSE:-0}"
YUM_OPTS="--assumeyes --nogpgcheck"
RPM_OPTS=""
CURL_OPTS=""
VENV_OPTS="--no-site-packages"

if [ "$VERBOSE" == "0" ]; then
    YUM_OPTS="$YUM_OPTS -q"
    YYOOM_OPTS=""
    RPM_OPTS="-q"
    CURL_OPTS="-s"
    VENV_OPTS="$VENV_OPTS -q"
fi

# Source in our variables (or overrides)
source ".anvilrc"
if [ -n "$SUDO_USER" ]; then
    USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    if [ -n "$USER_HOME" ]; then
        HOME_RC="${USER_HOME}/.anvilrc"
        if [ -f "$HOME_RC" ]; then
            source "$HOME_RC"
        fi
    fi
fi

dump_list()
{
    for var in "$@"; do
        for name in $var; do
            echo "  - $name"
        done
    done
}

bootstrap_rpm_packages()
{
    # NOTE(aababilov): the latter operations require some packages,
    # so, begin from installation
    if [ -n "$REQUIRES" ]; then
        echo -e "Installing system packages:"
        dump_list $REQUIRES
        yum install $YUM_OPTS $REQUIRES
        if [ "$?" != "0" ]; then
            echo -e "Failed installing!"
            return 1
        fi
    fi
    return 0
}

clean_pip()
{
    # https://github.com/pypa/pip/issues/982
    if [ -n "$SUDO_USER" ]; then
        rm -rf "/tmp/pip-build-$SUDO_USER"
    fi
}

bootstrap_epel()
{
    [ -z "$EPEL_RPM_URL" ] && return 0
    cache_and_install_rpm_url "$EPEL_RPM_URL"
    return $?
}

bootstrap_virtualenv()
{
    virtualenv $VENV_OPTS "$PWD/.venv"
    local pip="$PWD/.venv/bin/pip"
    $pip install -r requirements.txt -r test-requirements.txt
}

bootstrap_selinux()
{
    # See if selinux is on.
    if [ "$(getenforce)" == "Enforcing" ]; then
        # Ensure all yum api interacting binaries are ok to be used
        echo "Enabling selinux for yum like binaries."
        chcon -h "system_u:object_r:rpm_exec_t:s0" "$YYOOM_CMD"
    fi
}

run_smithy()
{
    PYTHON="$PWD/.venv/bin/python"
    exec "$PYTHON" anvil $ARGS
}

puke()
{
    cleaned_force=$(echo "$FORCE" | sed -e 's/\([A-Z]\)/\L\1/g;s/\s//g')
    if [[ "$cleaned_force" == "yes" ]]; then
        run_smithy
    else
        echo -e "To run anyway set FORCE=yes and rerun." >&2
        exit 1
    fi
}

needs_bootstrap()
{
    $BOOTSTRAP && return 0
    if [ ! -d "$PWD/.venv" ]; then
        return 1
    fi
    return 0
}

## Identify which bootstrap configuration file to use: either set
## explicitly (BSCONF_FILE) or determined based on the os distribution:
BSCONF_DIR="${BSCONF_DIR:-$(dirname $(readlink -f "$0"))/tools/bootstrap}"
get_os_info(){
    if [ "$(uname)" = "Linux" ] ; then
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
while [ "$#" != 0 ]; do
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

# Source immediately so that we can export the needed variables.
if [ -f "$BSCONF_FILE" ]; then
    source "$BSCONF_FILE"
fi

if ! needs_bootstrap; then
    clean_pip
    run_smithy
elif ! $BOOTSTRAP; then
    echo "This system needs to be updated in order to run anvil!" >&2
    echo "Running 'sudo $SMITHY_NAME --bootstrap' will attempt to do so." >&2
    puke
fi

## Bootstrap smithy
if [ "$(id -u)" != "0" ]; then
    echo "You must run '$SMITHY_NAME --bootstrap' with root privileges!" >&2
    exit 1
fi

if [ ! -f "$BSCONF_FILE" ]; then
    echo "Anvil has not been tested on distribution '$OSNAME'" >&2
    puke
fi

MIN_RELEASE=${MIN_RELEASE:?"Error: MIN_RELEASE is undefined!"}
SHORTNAME=${SHORTNAME:?"Error: SHORTNAME is undefined!"}
if [ "$RELEASE" != "$(greatest_version "$RELEASE" "$MIN_RELEASE")" ]; then
    echo "This script must be run on $SHORTNAME $MIN_RELEASE+ and not $SHORTNAME $RELEASE." >&2
    puke
fi

echo "Bootstrapping $SHORTNAME $RELEASE"
echo "Please wait..."
clean_pip
for step in ${STEPS:?"Error: STEPS is undefined!"}; do
    "bootstrap_${step}"
    if [ $? != 0 ]; then
        echo "Bootstrapping $SHORTNAME $RELEASE failed." >&2
        exit 1
    fi
done
clean_pip

mkdir -p -v /etc/anvil /usr/share/anvil
touch /var/log/anvil.log
if [ -n "$SUDO_UID" -a -n "SUDO_GID" ]; then
    chown -c "$SUDO_UID:$SUDO_GID" /etc/anvil /usr/share/anvil \
        /var/log/anvil.log
    [ -d .bootstrap ] && chown -R "$SUDO_UID:$SUDO_GID" .bootstrap
fi

echo "Bootstrapped for $SHORTNAME $RELEASE"
ARGS="-a moo"
run_smithy
