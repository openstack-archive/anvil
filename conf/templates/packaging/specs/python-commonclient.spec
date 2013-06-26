#encoding UTF-8
# Based on spec by:
# * Alessio Ababilov <aababilov@griddynamics.com>
#*
    version - version for RPM
    epoch - epoch for RPM
    clientname - keystone, nova, etc. (lowercase)
    apiname - Identity, Compute, etc. (first uppercase)
    requires - list of requirements for python-* package
*#

%global python_name ${clientname}client
%global os_version $version
%global tests_data_dir %{_datarootdir}/%{python_name}-tests/

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 5)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

Name:             python-%{python_name}
Summary:          OpenStack ${clientname.title()} Client
Version:          %{os_version}$version_suffix
Release:          $release%{?dist}
Epoch:            $epoch

Group:            Development/Languages
License:          Apache 2.0
Vendor:           OpenStack Foundation
URL:              http://www.openstack.org
Source0:          %{name}-%{os_version}.tar.gz

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}

BuildArch:        noarch
BuildRequires:    python-setuptools

%if 0%{?enable_doc}
BuildRequires:    python-sphinx
BuildRequires:    make
%endif

#for $i in $requires
Requires:        ${i}
#end for

%description
This is a client for the OpenStack $apiname API. There is a Python API (the
${clientname}client module), and a command-line script (${clientname}).


%if ! 0%{?no_tests}
%package tests
Summary:          Tests for OpenStack ${clientname.title()} Client
Group:            Development/Libraries

Requires:         %{name} = %{epoch}:%{version}-%{release}
Requires:         python-nose
Requires:         python-openstack-nose-plugin
Requires:         python-nose-exclude

#for $i in $test_requires
Requires:         ${i}
#end for

%description tests
This package contains unit and functional tests for OpenStack
${clientname.title()} Client, with runner.
%endif


%if 0%{?enable_doc}
%package doc
Summary:        Documentation for %{name}
Group:          Documentation
Requires:       %{name} = %{epoch}:%{version}-%{release}


%description doc
Documentation for %{name}.
%endif


%prep
%setup -q
#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for
#raw
touch AUTHORS ChangeLog
if [ ! -f HACKING* ]; then
    touch HACKING
fi

%build
%{__python} setup.py build


%install
rm -rf %{buildroot}

%{__python} setup.py install -O1 --skip-build --root %{buildroot}
# keystoneclient writes a strange catalog
rm -rf %{buildroot}/%{_usr}/*client

%if 0%{?enable_doc}
make -C docs html PYTHONPATH=%{buildroot}%{python_sitelib}
%endif

%if ! 0%{?no_tests}
# Package test environment
install -d -m 755 %{buildroot}%{tests_data_dir}
tar -czf "%{buildroot}%{tests_data_dir}/test_env.tgz" \
    --exclude-vcs  --exclude ./%{python_name} .
if [ -d "./{python_name}/tests"]; then
    tar -rzf "%{buildroot}%{tests_data_dir}/test_env.tgz" \
        ./%{python_name}/tests
fi

# Make simple test runner
cat > %{buildroot}%{_bindir}/%{python_name}-run-unit-tests <<"EOF"
#!/bin/bash
export NOSE_WITH_OPENSTACK=1
export NOSE_OPENSTACK_RED=0.05
export NOSE_OPENSTACK_YELLOW=0.025
export NOSE_OPENSTACK_SHOW_ELAPSED=1

# Create temporary directory, remove it on exit:
tmpdir=
cleanup_tmpdir()
{
    [ -z "$tmpdir" ] || rm -rf -- "$tmpdir"
    exit "$@"
}
tmpdir=$(mktemp -dt "${0##*/}.XXXXXXXX")
trap 'cleanup_tmpdir $?' EXIT
trap 'clenaup_tmpdir 143' HUP INT QUIT PIPE TERM

cd "$tmpdir"
tar -xzf "%{tests_data_dir}/test_env.tgz"
cp -a %{python_sitelib}/%{python_name} .

exec nosetests --openstack-color --verbosity=2 --detailed-errors \
#end raw
#for i in $exclude_tests
    --exclude "${i}" \
#end for
#raw
    "$@"

EOF
chmod 0755 %{buildroot}%{_bindir}/%{python_name}-run-unit-tests
%endif

%clean
rm -rf %{buildroot}


%files
%defattr(-,root,root,-)
%doc README* LICENSE* HACKING* ChangeLog AUTHORS
%{python_sitelib}/*
%{_bindir}/*
%exclude %{_bindir}/%{python_name}-run-unit-tests

%if ! 0%{?no_tests}
%files tests
%{tests_data_dir}
%{_bindir}/%{python_name}-run-unit-tests
%endif

%if 0%{?enable_doc}
%files doc
%defattr(-,root,root,-)
%doc docs/_build/html
%endif


%changelog
#end raw
