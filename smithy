#!/bin/bash

locale -a | grep -q -e "^en_US$" && export LANG="en_US"

shopt -s nocasematch

SMITHY_NAME=$(readlink -f "$0")
cd "$(dirname "$0")"

VERBOSE="${VERBOSE:-0}"
YUM_OPTS="--assumeyes --nogpgcheck"
YUM_CONFIG_MANAGER_OPTS=""
CURL_OPTS=""

# Give access to the system packages so that when clients get installed
# after installation that the virtualenv can access them to do things like
# install images, setup keystone...
VENV_OPTS="--system-site-packages"
VENV_DIR="$PWD/.venv"
VENV_ACTIVATE="$VENV_DIR/bin/activate"
PIP="$VENV_DIR/bin/pip"
YYOOM_CMD="$PWD/tools/yyoom"

if [ "$VERBOSE" == "0" ]; then
    YUM_OPTS="$YUM_OPTS -q"
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

yum_install()
{
    local requires=$@
    if [ "$VERBOSE" == "0" ]; then
        yum install $YUM_OPTS $requires > /dev/null 2>&1
    else
        yum install $YUM_OPTS $requires
    fi
    return $?
}

yum_remove()
{
    local remove=$@
    if [ "$VERBOSE" == "0" ]; then
        yum remove $YUM_OPTS $remove > /dev/null 2>&1
    else
        yum remove $YUM_OPTS $remove
    fi
    return $?
}

bootstrap_rpm_packages()
{
    if [ -n "$REQUIRES" ]; then
        echo -e "Installing system packages:"
        dump_list $REQUIRES
        echo "Please wait..."
        yum_install $REQUIRES
        if [ "$?" != "0" ]; then
            echo -e "Failed installing!"
            return 1
        fi
    fi
    if [ -n "$CONFLICTS" ]; then
        echo -e "Removing conflicting system packages:"
        dump_list $CONFLICTS
        echo "Please wait..."
        yum_remove $CONFLICTS
        if [ "$?" != "0" ]; then
            echo -e "Failed removing!"
            return 1
        fi
    fi
    return 0
}

clean_anvil_deps()
{
    # A previously failed anvil build which is not fully cleaned
    # up has the potential for leaving broken packages.  We disable
    # the anvil-deps repo on bootstrap to avoid subsequent yum failures
    # when pulling packages from this repo during bootstrap.
    yum-config-manager $YUM_CONFIG_MANAGER_OPTS --disable anvil-deps
}

clean_pip()
{
    # See: https://github.com/pypa/pip/issues/982
    if [ -n "$SUDO_USER" ]; then
        rm -rf "/tmp/pip-build-$SUDO_USER"
    fi
}

bootstrap_epel()
{
    # Installs the repository that will allow for installation of packages
    # from epel, see https://fedoraproject.org/wiki/EPEL for information
    # about what is epel.
    [ -z "$EPEL_RPM_URL" ] && return 0
    echo "Installing epel rpm from $EPEL_RPM_URL"
    cache_and_install_rpm_url "$EPEL_RPM_URL"
    return $?
}

bootstrap_repos()
{
    # Installs other repositories that will allow for installation of packages
    # from places other than epel. This allows for anvil to find dependencies
    # from other places (so anvil can avoid building those dependencies in the
    # first place).
    [ -z "$REPO_URLS" ] && return 0
    # If urls were provided but no directory, that's bad.
    [ -z "$REPO_DIR" ] && return 1
    for repo_url in $REPO_URLS; do
        echo "Installing repo file from $repo_url -> $REPO_DIR"
        local base_filename=$(basename $repo_url)
        local output_filename="$REPO_DIR/$base_filename"
        if [ "$VERBOSE" == "0" ]; then
            wget -q "$repo_url" -O "$output_filename"
        else
            wget "$repo_url" -O "$output_filename"
        fi
        if [ "$?" != "0" ]; then
            echo -e "Failed downloading $repo_url -> $output_filename"
            return 1
        fi
    done
    return 0
}

unsudo()
{
    # If a sudo user is active the given files/directories will be changed to
    # be owned by that user instead of the current root user, if no sudo user
    # is active, then nothing changes.
    if [ -n "$SUDO_UID" -a -n "$SUDO_GID" ]; then
        if [ "$VERBOSE" == "0" ]; then
            chown -R "$SUDO_UID:$SUDO_GID" $@
        else
            chown -R -c "$SUDO_UID:$SUDO_GID" $@
        fi
    fi
}

bootstrap_virtualenv()
{
    # Creates a virtualenv and then installs anvils requirements in it.
    echo "Setting up virtualenv in $VENV_DIR"
    virtualenv $VENV_OPTS "$VENV_DIR" || return 1
    unsudo $VENV_DIR
    local deps=$(cat requirements.txt | grep -v '^$\|^\s*\#' | sort)
    if [ -n "$deps" ]; then
        echo "Installing anvil dependencies in $VENV_DIR"
        dump_list $deps
        echo "Please wait..."
        if [ "$VERBOSE" == "0" ]; then
            $PIP install -r requirements.txt > /dev/null 2>&1
        else
            $PIP install -v -r requirements.txt
        fi
        if [ "$?" != "0" ]; then
            return 1
        fi
    fi
    unsudo $VENV_DIR
}

bootstrap_selinux()
{
    # See if selinux is on.
    echo "Enabling selinux for yum like binaries."
    if [ "$(getenforce)" == "Enforcing" ]; then
        # Ensure all yum api interacting binaries are ok to be used.
        chcon -h "system_u:object_r:rpm_exec_t:s0" "$YYOOM_CMD"
    fi
}

run_smithy()
{
    source "$VENV_ACTIVATE"
    local python=$(which python)
    exec "$python" anvil $ARGS
}

puke()
{
    local cleaned_force=$(echo "$FORCE" | sed -e 's/\([A-Z]\)/\L\1/g;s/\s//g')
    if [ "$cleaned_force" != "yes" ]; then
        echo -e "To run anyway set FORCE=yes and rerun." >&2
        exit 1
    fi
}

needs_bootstrap()
{
    # Checks if we need to perform the bootstrap phase.
    if [ "$BOOTSTRAP" == "true" ]; then
        return 0
    fi
    if [ ! -d "$VENV_DIR" -o ! -f "$VENV_ACTIVATE" -o ! -f "$PIP" ]; then
        return 0
    fi
    return 1
}

rpm_is_installed()
{
    # Checks if an rpm is already installed.
    local name=$(basename "$1")
    rpm -q "${name%.rpm}" &>/dev/null
    return $?
}

cache_and_install_rpm_url()
{
    # Downloads an rpm from a url and then installs it (if it's not already
    # installed).
    url=${1:?"Error: rpm url is undefined!"}
    cachedir=${RPM_CACHEDIR:-'/tmp'}
    rpm=$(basename "$url")
    if rpm_is_installed "$rpm"; then
        return 0
    fi
    if [ ! -f "$cachedir/$rpm" ]; then
        echo -e "Downloading ${rpm} to ${cachedir}"
        curl $CURL_OPTS "$url" -o "$cachedir/$rpm" || return 1
    fi
    echo -e "Installing $cachedir/$rpm"
    yum_install "$cachedir/$rpm"
    return $?
}

greatest_version()
{
    for arg in "$@"; do
        echo "$arg"
    done | sort --version-sort --reverse | head -n1
}

smallest_version()
{
    for arg in "$@"; do
        echo "$arg"
    done | sort --version-sort | head -n1
}

## Identify which bootstrap configuration file to use: either set
## explicitly (BSCONF_FILE) or determined based on the os distribution:
BSCONF_DIR="${BSCONF_DIR:-$(dirname $(readlink -f "$0"))/tools/bootstrap}"
get_os_info()
{
    if [ "$(uname)" = "Linux" ] ; then
        if [ -f /etc/redhat-release ] ; then
            PKG="rpm"
            OSNAME=`cat /etc/redhat-release`
            OSDIST=`cat /etc/redhat-release | sed -e 's/release.*$//g;s/\s//g'`
            if [ "$OSDIST" == "CentOSLinux" ] ; then
                OSDIST="CentOS"
            fi
            PSUEDONAME=`cat /etc/redhat-release | sed s/.*\(// | sed s/\)//`
            RELEASE=`cat /etc/redhat-release | sed s/.*release\ // | sed s/\ .*//`
            MAJOR_RELEASE=`cat /etc/redhat-release | sed s/.*release\ // | sed s/\ .*// | cut -f1 -d"."`
        elif [ -f /etc/debian_version ] ; then
            PKG="deb"
            OSDIST=`cat /etc/lsb-release | grep '^DISTRIB_ID' | awk -F= '{ print $2 }'`
            PSUEDONAME=`cat /etc/lsb-release | grep '^DISTRIB_CODENAME' | awk -F= '{ print $2 }'`
            RELEASE=`cat /etc/lsb-release | grep '^DISTRIB_RELEASE' | awk -F= '{ print $2 }'`
            MAJOR_RELEASE=`cat /etc/lsb-release | grep '^DISTRIB_RELEASE' | awk -F= '{ print $2 }' | cut -f1 -d"."`
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
else
    clean_anvil_deps
fi

if [ "$BOOTSTRAP" == "false" ]; then
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
else
    MIN_RELEASE=${MIN_RELEASE:?"Error: MIN_RELEASE is undefined!"}
    SHORTNAME=${SHORTNAME:?"Error: SHORTNAME is undefined!"}
    if [ "$MIN_RELEASE" != "$RELEASE" ]; then
        if [ "$RELEASE" != "$(greatest_version "$RELEASE" "$MIN_RELEASE")" ]; then
            echo "This script must be run on $SHORTNAME $MIN_RELEASE and newer and not $SHORTNAME $RELEASE." >&2
            puke
        fi
    fi
    if [ -n "$MAX_RELEASE" ]; then
        if [ "$MAX_RELEASE" != "$RELEASE" ]; then
            if [ "$MAX_RELEASE" == "$(smallest_version "$MAX_RELEASE" "$RELEASE")" ]; then
                echo "This script must be run on $SHORTNAME $MAX_RELEASE or older and not $SHORTNAME $RELEASE." >&2
                puke
            fi
        fi
    fi
fi

# If we got here then we must be in force mode, setup with the default configuration
# file for unknown distros...
if [ ! -f "$BSCONF_FILE" ]; then
    BSCONF_FILE="$BSCONF_DIR/Unknown"
    SHORTNAME="$OSDIST"
    source "$BSCONF_FILE"
fi

echo "Bootstrapping $SHORTNAME $RELEASE"
echo "Please wait..."
clean_pip
for step in ${STEPS:?"Error: STEPS is undefined!"}; do
    echo "--- Running bootstrap step $step ---"
    "bootstrap_${step}"
    if [ $? != 0 ]; then
        echo "Bootstrapping $SHORTNAME $RELEASE failed." >&2
        exit 1
    fi
done
clean_pip

# Anvil writes configurations in these locations, make sure they are created
# and that the user running this script can actually access those files (even
# later if they are not running with sudo).
mkdir -p -v /etc/anvil /usr/share/anvil
touch /var/log/anvil.log
unsudo /etc/anvil /usr/share/anvil /var/log/anvil.log

echo "Bootstrapped for $SHORTNAME $RELEASE"
ARGS="-a moo"
run_smithy
