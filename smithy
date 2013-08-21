#!/bin/bash

locale -a | grep -q -e "^en_US$" && export LANG="en_US"

shopt -s nocasematch

SMITHY_NAME=$(readlink -f "$0")
cd "$(dirname "$0")"

VERBOSE="${VERBOSE:-0}"
PY2RPM_CMD="$PWD/tools/py2rpm"
YUMFIND_CMD="$PWD/tools/yumfind"
PIPDOWNLOAD_CMD="$PWD/tools/pip-download"

YUM_OPTS="--assumeyes --nogpgcheck"
RPM_OPTS=""
CURL_OPTS=""

# Colors supported??
COLOR_SUPPORT=`tput colors`

if [ $COLOR_SUPPORT -ge 8 ]; then
    ESC_SEQ="\x1b["
    COL_RESET=$ESC_SEQ"39;49;00m"
    COL_GREEN=$ESC_SEQ"32;01m"
    COL_RED=$ESC_SEQ"31;01m"
    COL_YELLOW=$ESC_SEQ"33;01m"
else
    ESC_SEQ=""
    COL_RESET=""
    COL_GREEN=""
    COL_RED=""
    COL_YELLOW=""
fi

if [ "$VERBOSE" == "0" ]; then
    YUM_OPTS="$YUM_OPTS -q"
    RPM_OPTS="-q"
    CURL_OPTS="-s"
fi

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

clean_pip()
{
    # https://github.com/pypa/pip/issues/982
    if [ -n "$SUDO_USER" ]; then
        rm -rf /tmp/pip-build-$SUDO_USER
    fi
}

rpm_is_installed()
{
    local name="$(basename "$1")"
    rpm $RPM_OPTS "${name%.rpm}" &>/dev/null
    return $?
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
        echo -e "Downloading ${COL_GREEN}${rpm}${COL_RESET} to ${COL_GREEN}${cachedir}${COL_RESET}"
        curl $CURL_OPTS $url -o "$cachedir/$rpm" || return 1
    fi
    echo -e "Installing ${COL_GREEN}$cachedir/$rpm${COL_RESET}"
    yum install $YUM_OPTS "$cachedir/$rpm"
    return $?
}

bootstrap_epel()
{
    [ -z "$EPEL_RPM_URL" ] && return 0
    cache_and_install_rpm_url $EPEL_RPM_URL
    return $?
}

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
        echo -e "Installing ${COL_GREEN}system${COL_RESET} packages:"
        dump_list "$REQUIRES"
        yum install $YUM_OPTS $REQUIRES
        if [ "$?" != "0" ]; then
            echo -e "${COL_RED}Failed installing!${COL_RESET}"
            return 1
        fi
    fi

    # Remove any known conflicting packages
    CONFLICTS=$(python -c "import yaml
packages = set()
try:
    for i in yaml.safe_load(open('$DISTRO_CONFIG'))['components'].itervalues():
        for j in i.get('conflicts', []):
            packages.add(j.get('name'))
except KeyError:
    pass
for pkg in packages:
    if pkg:
        print pkg
")
    if [ -n "$CONFLICTS" ]; then
        echo -e "Removing ${COL_YELLOW}conflicting${COL_RESET} packages:"
        dump_list "$CONFLICTS"
        yum erase $YUM_OPTS $CONFLICTS
    fi
}

bootstrap_selinux()
{
    # See if selinux is on.
    if [ `getenforce` == "Enforcing" ]; then
        # Ensure all yum api interacting binaries are ok to be used
        echo "Enabling selinux for yum like binaries."
        chcon -h "system_u:object_r:rpm_exec_t:s0" "$YUMFIND_CMD"
        chcon -h "system_u:object_r:rpm_exec_t:s0" "$PWD/tools/yyoom"
    fi
}

bootstrap_python_rpms()
{
    echo -e "Bootstrapping ${COL_GREEN}python${COL_RESET} rpms."
    local package_map=$(python -c "import yaml
try:
    for k, v in yaml.safe_load(open('$DISTRO_CONFIG'))['dependency_handler']['package_map'].iteritems():
        print '%s==%s' % (k, v)
except KeyError:
    pass
")
    local python_names=$(cat requirements.txt test-requirements.txt | sed -r -e 's/#.*$//' | sort -u)
    local bootstrap_dir="$(readlink -f ./.bootstrap/)"
    local missing_packages=""
    local found_packages=""
    for name in $python_names; do
        local pkg_name=$("$PY2RPM_CMD" --package-map $package_map --convert "$name" | while read req pack; do echo $pack; done  | head -n1 | tr -s ' ' | cut -d' ' -f1)
        local yum_name=$("$YUMFIND_CMD" -p "$pkg_name,$name")
        if [ -n "$yum_name" ]; then
            found_packages="$found_packages $yum_name"
        else
            missing_packages="$missing_packages $name"
        fi
    done
    if [ -n "$found_packages" ]; then
        echo -e "Installing ${COL_GREEN}available${COL_RESET} python requirements found as packages:"
        dump_list "$found_packages"
        yum install $YUM_OPTS $found_packages
        if [ "$?" != "0" ]; then
            echo -e "${COL_RED}Failed installing!${COL_RESET}"
            return 1
        fi
    fi
    if [ -z "$missing_packages" ]; then
        return 0
    fi
    echo -e "Building ${COL_YELLOW}missing${COL_RESET} python requirements:"
    dump_list "$missing_packages"
    local pip_tmp_dir="$bootstrap_dir/pip-download"
    mkdir -p "$pip_tmp_dir"

    echo "Downloading..."
    $PIPDOWNLOAD_CMD -d "$pip_tmp_dir" $missing_packages | grep "^Saved"
    echo "Building RPMs..."
    local rpm_names=$("$PY2RPM_CMD"  --package-map $package_map --scripts-dir "conf/templates/packaging/scripts" --rpm-base "$bootstrap_dir/rpmbuild" -- "$pip_tmp_dir/"* 2>/dev/null |
        awk '/^Wrote: /{ print $2 }' | grep -v '.src.rpm' | sort -u)
    if [ -z "$rpm_names" ]; then
        echo -e "${COL_RED}No binary RPMs were built!${COL_RESET}"
        return 1
    fi
    local rpm_base_names=""
    for rpm in $rpm_names; do
        rpm_base_names="$rpm_base_names $(basename $rpm)"
    done
    echo -e "Installing ${COL_YELLOW}missing${COL_RESET} python requirement packages:"
    dump_list "$rpm_base_names"
    yum install $YUM_OPTS $rpm_names
    if [ "$?" != "0" ]; then
        echo -e "${COL_RED}Failed installing!${COL_RESET}"
        return 1
    fi
    rm -rf "$pip_tmp_dir"
    rm -rf "$bootstrap_dir/rpmbuild/"{BUILD,SOURCES,SPECS,BUILDROOT}
    return 0
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
    if [ ! -f "$BSCONF_FILE" ]; then
        return 1
    fi
    # Used to tell if the file have changed
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
        echo -e "To run anyway set ${COL_YELLOW}FORCE=yes${COL_RESET} and rerun." >&2
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

# Source immediately so that we can export the needed variables.
if [ -f "$BSCONF_FILE" ]; then
    source $BSCONF_FILE
    export REQUIRED_PACKAGES="$REQUIRES"
fi

if ! needs_bootstrap; then
    clean_pip
    run_smithy
    clean_pip
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
BC_OK=$(echo "$RELEASE < $MIN_RELEASE" | bc)
if [ "$BC_OK" == "1" ]; then
    echo "This script must be run on $SHORTNAME $MIN_RELEASE+ and not $SHORTNAME $RELEASE." >&2
    puke
fi

echo "Bootstrapping $SHORTNAME $RELEASE"
echo "Please wait..."
clean_pip
for step in ${STEPS:?"Error: STEPS is undefined!"}; do
    bootstrap_${step}
    if [ $? != 0 ]; then
        echo "Bootstrapping $SHORTNAME $RELEASE failed." >&2
        exit 1
    fi
done
clean_pip

# Write the checksums of the bootstrap file
# which if new requirements are added will cause new checksums
# and a new dependency install...
checksum=$(get_checksums)
for i in $BOOT_FILES; do
    echo -e $checksum > $i
done

mkdir -p -v /etc/anvil /usr/share/anvil
if [ -n "$SUDO_UID" -a -n "SUDO_GID" ]; then
    chown -c "$SUDO_UID:$SUDO_GID" /etc/anvil /usr/share/anvil
    [ -d .bootstrap ] && chown -R "$SUDO_UID:$SUDO_GID" .bootstrap
fi

echo "Bootstrapped for $SHORTNAME $RELEASE"
ARGS="-a moo"
run_smithy
