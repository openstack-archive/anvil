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

Name:             python-${clientname}client
Summary:          OpenStack ${clientname.title()} Client
Version:          $version
Release:          1%{?dist}
Epoch:            $epoch

Group:            Development/Languages
License:          Apache 2.0
Vendor:           OpenStack Foundation
URL:              http://www.openstack.org
Source0:          %{name}-%{version}.tar.gz

BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}

BuildArch:        noarch
BuildRequires:    python-setuptools

%if 0%{?enable_doc}
BuildRequires:    python-sphinx make
%endif

#for $i in $requires
${i}
#end for

%description
This is a client for the OpenStack $apiname API. There is a Python API (the
${clientname}client module), and a command-line script (${clientname}).

#raw
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
%doc README* LICENSE* HACKING*
%{python_sitelib}/*
%{_bindir}/*


%if 0%{?enable_doc}
%files doc
%defattr(-,root,root,-)
%doc docs/_build/html
%endif


%changelog
#end raw
