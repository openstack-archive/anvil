%global python_name ironic
%global daemon_prefix openstack-ironic
%global os_version ${version}

%global with_doc %{!?_without_doc:1}%{?_without_doc:0}

%if 0%{?rhel} && 0%{?rhel} <= 6
%{!?__python2: %global __python2 /usr/bin/python2}
%{!?python2_sitelib: %global python2_sitelib %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python2_sitearch: %global python2_sitearch %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
%endif

Name:		openstack-ironic
Summary:	OpenStack Baremetal Hypervisor API (ironic)
Version:	%{os_version}$version_suffix
Release:	$release%{?dist}
License:	ASL 2.0
Group:		System Environment/Base
URL:		http://www.openstack.org
Source0:	%{python_name}-%{os_version}.tar.gz


Source10:	openstack-ironic-api.init
Source11:	openstack-ironic-conductor.init

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}

BuildArch:        noarch
BuildRequires:	  python-setuptools
BuildRequires:	  python2-devel
BuildRequires:	  python-pbr
BuildRequires:	  openssl-devel
BuildRequires:	  libxml2-devel
BuildRequires:	  libxslt-devel
BuildRequires:	  gmp-devel
BuildRequires:	  python-sphinx



%prep
%setup -q -n %{python_name}-%{os_version}

#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for

#raw
%build
%{__python2} setup.py build

%install
%{__python2} setup.py install -O1 --skip-build --root=%{buildroot}

#end raw

# install init files
mkdir -p %{buildroot}%{_unitdir}
install -p -D -m 755 %{SOURCE10} %{buildroot}%{_initrddir}/openstack-ironic-api
install -p -D -m 755 %{SOURCE11} %{buildroot}%{_initrddir}/openstack-ironic-conductor


mkdir -p %{buildroot}%{_sharedstatedir}/ironic/
mkdir -p %{buildroot}%{_sysconfdir}/ironic/rootwrap.d

#Populate the conf dir
install -p -D -m 640 etc/ironic/ironic.conf.sample %{buildroot}/%{_sysconfdir}/ironic/ironic.conf
install -p -D -m 640 etc/ironic/policy.json %{buildroot}/%{_sysconfdir}/ironic/policy.json
install -p -D -m 640 etc/ironic/rootwrap.conf %{buildroot}/%{_sysconfdir}/ironic/rootwrap.conf
install -p -D -m 640 etc/ironic/rootwrap.d/* %{buildroot}/%{_sysconfdir}/ironic/rootwrap.d/


%description
Ironic provides an API for management and provisioning of physical machines

%package -n python-ironic
Summary: Ironic Python libraries
Group: Applications/System

#for $i in $requires
Requires:        ${i}
#end for

%description -n python-ironic
This package contains the %{name} Python library.

%files -n python-ironic
%defattr(-,root,root,-)
%doc LICENSE
%{python_sitelib}/ironic*
%exclude %{python_sitelib}/%{python_name}/tests

%package common
Summary: Ironic common
Group: System Environment/Base

#for $i in $requires
Requires:         ${i}
#end for

%description common
Components common to all OpenStack Ironic services

%files common
%doc README.rst LICENSE
%{_bindir}/ironic-dbsync
%{_bindir}/ironic-rootwrap
%config(noreplace) %attr(-,root,ironic) %{_sysconfdir}/ironic
%attr(-,ironic,ironic) %{_sharedstatedir}/ironic

%pre common
#raw
getent group ironic >/dev/null || groupadd -r ironic
getent passwd ironic >/dev/null || \
    useradd -r -g ironic -d %{_sharedstatedir}/ironic -s /sbin/nologin \
-c "OpenStack Ironic Daemons" ironic
exit 0
#end raw

%package api
Summary: The Ironic API
Group: System Environment/Base

Requires: %{name}-common = %{version}-%{release}
Requires: python-%{name} = %{version}-%{release}

%description api
Ironic API for management and provisioning of physical machines


%files api
%doc LICENSE
%{_bindir}/ironic-api
%{_initrddir}/openstack-ironic-api

%package conductor
Summary: The Ironic Conductor
Group: System Environment/Base

Requires: %{name}-common = %{version}-%{release}
Requires: python-%{name} = %{version}-%{release}

%description conductor
Ironic Conductor for management and provisioning of physical machines


%files conductor
%doc LICENSE
%{_bindir}/ironic-conductor
%{_initrddir}/openstack-ironic-conductor

%changelog
