%global modulename neutron_fwaas
%global servicename neutron-fwaas
%global type FWaaS
%global python_name neutron-fwaas
%global daemon_prefix neutron-fwaas
%global os_version ${version}
%global no_tests $no_tests
%global tests_data_dir %{_datarootdir}/%{python_name}-tests

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

%if ! 0%{?overwrite_configs}
%global configfile %config(noreplace)
%else
%global configfile %config
%endif

Name:           openstack-%{servicename}
Version:        %{os_version}$version_suffix
Release:        $release%{?dist}
Epoch:          $epoch
Summary:        Openstack Networking %{type} plugin

License:        ASL 2.0
URL:            http://launchpad.net/neutron/
Source0:        %{python_name}-%{os_version}.tar.gz

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}

BuildArch:      noarch
BuildRequires:  python2-devel
BuildRequires:  python-pbr
BuildRequires:  python-setuptools

Requires:       python-%{servicename} = %{epoch}:%{version}-%{release}
Requires:       openstack-neutron >= %{epoch}:%{version}-%{release}

%description
This is a %{type} service plugin for Openstack Neutron (Networking) service.


%package -n python-%{servicename}
Summary:        Neutron %{type} Python libraries
Group:          Applications/System

Requires:       python-neutron >= %{epoch}:%{version}-%{release}
#for $i in $requires
Requires:         ${i}
#end for

#for $i in $conflicts
Conflicts:       ${i}
#end for



%description -n python-%{servicename}
This is a %{type} service plugin for Openstack Neutron (Networking) service.

This package contains the Neutron %{type} Python library.


%package -n python-%{servicename}-tests
Summary:        Neutron %{type} tests
Group:          Applications/System

Requires:       python-%{servicename} = %{epoch}:%{version}-%{release}


%description -n python-%{servicename}-tests
This is a %{type} service plugin for Openstack Neutron (Networking) service.

This package contains Neutron %{type} test files.


%prep
%setup -q -n %{python_name}-%{os_version}

#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for

%build

export PBR_VERSION=$version
export SKIP_PIP_INSTALL=1
%{__python} setup.py build


%install

export PBR_VERSION=$version
export SKIP_PIP_INSTALL=1
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

%if ! 0%{?usr_only}
# Move config files to proper location
install -d -m 755 %{buildroot}%{_sysconfdir}/neutron
mv %{buildroot}/usr/etc/neutron/*.ini %{buildroot}%{_sysconfdir}/neutron

# Create and populate distribution configuration directory for L3/VPN agent
mkdir -p %{buildroot}%{_datadir}/neutron/l3_agent
ln -s %{_sysconfdir}/neutron/fwaas_driver.ini %{buildroot}%{_datadir}/neutron/l3_agent/fwaas_driver.conf
%endif


%files
%license LICENSE
%doc AUTHORS CONTRIBUTING.rst README.rst
%if ! 0%{?usr_only}
%config%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/fwaas_driver.ini
%{_datadir}/neutron/l3_agent/*.conf
%endif

%files -n python-%{servicename}
%{python_sitelib}/%{modulename}
%{python_sitelib}/%{modulename}-%{version}-py%{python2_version}.egg-info
%exclude %{python_sitelib}/%{modulename}/tests


%files -n python-%{servicename}-tests
%{python_sitelib}/%{modulename}/tests


%changelog
