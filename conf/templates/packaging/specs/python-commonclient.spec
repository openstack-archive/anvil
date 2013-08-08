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
%if ! (0%{?fedora} > 12 || 0%{?rhel} > 5)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

%global os_version $version

Name:             python-${clientname}client
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

#for $i in $requires
Requires:        ${i}
#end for

%description
This is a client for the OpenStack $apiname API. There is a Python API (the
${clientname}client module), and a command-line script (${clientname}).

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


%clean
rm -rf %{buildroot}


%files
%defattr(-,root,root,-)
%doc README* LICENSE* HACKING* ChangeLog AUTHORS
%{python_sitelib}/*
%{_bindir}/*


%if 0%{?enable_doc}
%files doc
%defattr(-,root,root,-)
%doc docs/_build/html
%endif


%changelog
#end raw
