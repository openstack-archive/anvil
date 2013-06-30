#!/bin/bash

shopt -s nocasematch

SMITHY_NAME=$(readlink -f "$0")
cd "$(dirname "$0")"

VERBOSE="${VERBOSE:-0}"
PY2RPM_CMD="$PWD/tools/py2rpm"
YUMFIND_CMD="$PWD/tools/yumfind"

YUM_OPTS="--assumeyes --nogpgcheck"
PIP_CMD=""
PIP_OPTS=""
RPM_OPTS=""
CURL_OPTS=""

if [ "$VERBOSE" == "0" ]; then
    YUM_OPTS="$YUM_OPTS -q"
    PIP_OPTS="-q"
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

find_pip()
{
    if [ -n "$PIP_CMD" ]; then
        return
    fi
    # Handle how RHEL likes to rename it.
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
        echo "Downloading $rpm to $cachedir..."
        curl $CURL_OPTS $url -o "$cachedir/$rpm" || return 1
    fi
    yum_install "$cachedir/$rpm"
    return $?
}

yum_install()
{
    local rpm_path=$1
    output=$(yum install $YUM_OPTS "$rpm_path" 2>&1)
    rc=$?
    if [ -n "$output" ]; then
        if [[ ! "$output" =~ "Nothing to do" ]]; then
            echo $output
        fi
    fi
    if [ "$rc" != "0" ]; then
        if [[ "$output" =~ "Nothing to do" ]]; then
            # Not really a problem.
            return 0
        fi
    fi
    return $rc
}

bootstrap_epel()
{
    [ -z "$EPEL_RPM_URL" ] && return 0
    cache_and_install_rpm_url $EPEL_RPM_URL
    return $?
}

bootstrap_rpm_packages()
{
    # NOTE(aababilov): the latter operations require some packages,
    # so, begin from installation
    if [ -n "$REQUIRES" ]; then
        echo "Installing packages: $(echo $REQUIRES)"
        for rpm in $REQUIRES; do
            yum_install "$rpm"
            if [ "$?" != "0" ]; then
                echo "Failed installing $rpm"
                return 1
            fi
        done
    fi

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
        echo "Removing conflicting packages: $(echo $CONFLICTS)"
        yum erase $YUM_OPTS $CONFLICTS
    fi
}

bootstrap_python_rpms()
{
    local package_map=$(python -c "import yaml
try:
    for k, v in yaml.safe_load(open('$DISTRO_CONFIG'))['dependency_handler']['package_map'].iteritems():
        print '%s==%s' % (k, v)
except KeyError:
    pass
")
    local python_names=$(cat requirements.txt test-requirements.txt | sed -r -e 's/#.*$//' | sort -u)
    echo "Attemping to install python requirements: $(echo $python_names)"
    local missing_packages=""
    local found_packages=""
    for name in $python_names; do
        local pkg_name=$("$PY2RPM_CMD" --package-map $package_map --convert "$name" | while read req pack; do echo $pack; done  | head -n1 | tr -s ' ' | cut -d' ' -f1)
        local yum_name=$("$YUMFIND_CMD" "$pkg_name" "$name")
        if [ -n "$yum_name" ]; then
            found_packages="$found_packages $yum_name"
        else
            missing_packages="$missing_packages $name"
        fi
    done
    if [ -n "$found_packages" ]; then
        echo "Attemping to install python requirements found as packages: $(echo $found_packages)"
        yum install $YUM_OPTS $found_packages
        if [ "$?" != "0" ]; then
            echo "Failed installing $(echo $found_packages)"
            return 1
        fi
    fi
    if [ -z "$missing_packages" ]; then
        return 0
    fi
	echo "Building missing python requirements: $(echo $missing_packages)"
    local pip_tmp_dir=$(mktemp -d)
    find_pip
    local pip_opts="$PIP_OPTS -U -I"
    echo "Downloading..."
    $PIP_CMD install $pip_opts $missing_packages --download "$pip_tmp_dir"
    echo "Building RPMs..."
    local rpm_names=$("$PY2RPM_CMD"  --package-map $package_map -- "$pip_tmp_dir/"* 2>/dev/null |
        awk '/^Wrote: /{ print $2 }' | grep -v '.src.rpm' | sort -u)
    if [ -z "$rpm_names" ]; then
        echo "No binary RPMs were built!"
        return 1
    fi
    local rpm_base_names=""
    for rpm in $rpm_names; do
        rpm_base_names="$rpm_base_names $(basename $rpm)"
    done
    echo "Installing missing python requirement packages: $(echo $rpm_base_names)"
    yum install $YUM_OPTS $rpm_names
    if [ "$?" != "0" ]; then
        echo "Failed installing $(echo $rpm_base_names)"
        return 1
    fi
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
    exit 1
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
fi

echo "Success! Bootstrapped for $SHORTNAME $RELEASE"
exit 0
