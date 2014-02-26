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
%global no_tests $no_tests
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

#if $clientname == 'neutron'
Provides:       python-quantumclient = %{epoch}:%{version}-%{release}
Obsoletes:      python-quantumclient < %{epoch}:%{version}-%{release}
#end if

BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}

BuildArch:        noarch
BuildRequires:    python-setuptools

%if 0%{?enable_doc}
BuildRequires:    python-sphinx
BuildRequires:    make
%endif

# Python requirements:
#for $i in $requires
Requires:        ${i}
#end for

%description
This is a client for the OpenStack $apiname API. There's a Python API
(the ${clientname}client module), and a command-line script (${clientname}).
Each implements 100% of the OpenStack $apiname API.


%if ! 0%{?no_tests}
%package tests
Summary:          Tests for OpenStack ${clientname.title()} Client
Group:            Development/Libraries

Requires:         %{name} = %{epoch}:%{version}-%{release}

# Test requirements:
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
#end raw
#include $part_fn("install_tests.sh")
#raw
%endif

for file in README* LICENSE* HACKING* ChangeLog AUTHORS "%{buildroot}%{_mandir}"/man*/*; do
    [ -f "$file" ] && echo "%%doc $file" >> doc_files.txt
done


%clean
rm -rf %{buildroot}


%files -f doc_files.txt
%defattr(-,root,root,-)
%{python_sitelib}/*
%{_bindir}/*
%exclude %{_bindir}/%{python_name}-make-test-env

%if ! 0%{?no_tests}
%files tests
%{tests_data_dir}
%{_bindir}/%{python_name}-make-test-env
%endif

%if 0%{?enable_doc}
%files doc
%defattr(-,root,root,-)
%doc docs/_build/html
%endif


%changelog
#end raw
