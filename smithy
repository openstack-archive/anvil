#!/bin/bash

shopt -s nocasematch

SMITHY_NAME=$(readlink -f "$0")
cd "$(dirname "$0")"

VERBOSE="${VERBOSE:-0}"
PY2RPM_CMD="$PWD/tools/py2rpm"

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
    output=$(yum install $YUM_OPTS "$@" 2>&1)
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

bootstrap_packages()
{
    CONFLICTS=$(python -c "import yaml
try:
    for i in yaml.safe_load(open('$DISTRO_CONFIG'))['components'].itervalues():
        for j in i.get('conflicts', []):
            print j.get('name')
except KeyError:
    pass
" | sort -u)
    if [ -n "$CONFLICTS" ]; then
        echo "Removing conflicting packages: $(echo $CONFLICTS)"
        yum erase $YUM_OPTS $CONFLICTS
    fi
    # NOTE(aababilov): the latter operations require some packages,
    # so, BOOTSTRAP_REQUIRES was introduced
    if [ -n "$BOOTSTRAP_REQUIRES" ]; then
        echo "Installing bootstrap requirements: $(echo $BOOTSTRAP_REQUIRES)"
        if ! yum install $YUM_OPTS $BOOTSTRAP_REQUIRES; then
            return 1
        fi
    fi
    local spec_filename=~/rpmbuild/SPECS/anvil-deps.spec
    install -D -m 644 conf/templates/packaging/specs/anvil-deps.spec "$spec_filename"

    local package_map=$(python -c "import yaml
try:
    for k, v in yaml.safe_load(open('$DISTRO_CONFIG'))['dependency_handler']['package_map'].iteritems():
        print '%s==%s' % (k, v)
except KeyError:
    pass
")
    local python_names=$(sed -r -e 's/#.*$//' requirements.txt test-requirements.txt)
    local rpm_names="$("$PY2RPM_CMD" --package-map $package_map --convert $python_names |
        sort -u)"

    export template_version="$(awk '/^version/{ print $3 }' ./setup.cfg)"
    export template_requires="$(
        for i in $REQUIRES; do echo "Requires:    $i"; done;
        echo "$rpm_names")"

    perl -i -pe 's/\$(\w+)/$ENV{"template_$1"}/g' "$spec_filename"
    deps_rpm=$(rpmbuild -bb "$spec_filename" 2>/dev/null |
        awk '/^Wrote: /{ print $2 }')
    if [ ! -e "$deps_rpm" ]; then
        echo "Cannot build Anvil dependencies RPM"
        return 1
    fi
    # NOTE(aababilov): if a package is installed, but doesn't belong to
    # a repository, yum reports it as 'Unsatisfied dependency'
    # That's not a problem: we will treat them as satisfying
    missing_rpms="$(yum -q deplist "$deps_rpm" |
        grep 'Unsatisfied' -B 1 |
        awk '/dependency:/{ print $2 }')"
    # Build and install missing packages
    local missing_python=""
    for python_name in $python_names; do
        rpm_name=$("$PY2RPM_CMD" --package-map $package_map --convert $python_name |
            awk '{ print $2; exit }')
        if ! rpm_is_installed "$rpm_name" && echo "$missing_rpms" | grep -q "^$rpm_name\$"; then
            missing_python="$missing_python $python_name"
        fi
    done
    ! rpm_is_installed anvil-deps || yum erase $YUM_OPTS anvil-deps
    if [ -n "$missing_python" ]; then
        # Some RPMs are not available, try to build them on fly.
        # First download them...
        local pip_tmp_dir=$(mktemp -d)
        find_pip
        local pip_opts="$PIP_OPTS -U -I"
        echo "Downloading missing Python requirements:$missing_python"
        $PIP_CMD install $pip_opts $missing_python --download "$pip_tmp_dir"
        # Now build them
        echo "Building RPMs for$missing_python"
        local rpm_names=$("$PY2RPM_CMD" --binary-only --package-map $package_map -- "$pip_tmp_dir/"* 2>/dev/null |
            awk '/^Wrote: /{ print $2 }')
        rm -rf "$pip_tmp_dir"
        if [ -z "$rpm_names" ]; then
            echo "No binary RPMs were built for$missing_python"
            return 1
        fi
        echo "Installing missing Python requirement packages:"
        for i in $rpm_names; do
            echo -e "\t"$i
        done
        # NOTE(aababilov): install the packages in one yum command
        # because they can depend on each other
        if ! yum_install $rpm_names; then
            return 1
        fi
    fi
    echo "Installing Anvil dependencies"
    yum_install "$deps_rpm"
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
