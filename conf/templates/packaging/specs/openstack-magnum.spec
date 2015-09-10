%global modulename magnum
%global servicename magnum
%global python_name magnum
%global daemon_prefix openstack-magnum
%global os_version ${version}
%global no_tests $no_tests
%global tests_data_dir %{_datarootdir}/%{python_name}-tests

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

%if ! 0%{?overwrite_configs}
%global configfile %config(noreplace)
%else
%global configfile %verify(mode)
%endif

Name:           openstack-%{servicename}
Version:        %{os_version}$version_suffix
Release:        $release%{?dist}
Epoch:          $epoch
Summary:        Openstack Networking %{type} plugin

License:        ASL 2.0
URL:            http://launchpad.net/neutron/
Source0:        %{python_name}-%{os_version}.tar.gz


Source1:        openstack-magnum-api.service
Source2:        openstack-magnum-conductor.service

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}

BuildArch:      noarch
BuildRequires:  python2-devel
BuildRequires:  python-pbr
BuildRequires:  python-setuptools

Requires:       python-%{servicename} = %{epoch}:%{version}-%{release}
Requires:       openstack-magnum >= %{epoch}:%{version}-%{release}

%description
Magnum is an OpenStack project which offers container orchestration engines for deploying and managing containers as first class resources in OpenStack.


%package -n python-%{servicename}
Summary:        Neutron %{type} Python libraries
Group:          Applications/System

Requires:       python-magnum >= %{epoch}:%{version}-%{release}
#for $i in $requires
Requires:         ${i}
#end for

#for $i in $conflicts
Conflicts:       ${i}
#end for



%description -n python-%{servicename}
Magnum is an OpenStack project which offers container orchestration engines for deploying and managing containers as first class resources in OpenStack.

This package contains the Magnum Python library.


%package -n python-%{servicename}-tests
Summary:        Neutron %{type} tests
Group:          Applications/System

Requires:       python-%{servicename} = %{epoch}:%{version}-%{release}


%description -n python-%{servicename}-tests
Magnum is an OpenStack project which offers container orchestration engines for deploying and managing containers as first class resources in OpenStack.

This package contains Magnum test files.


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
install -d -m 755 %{buildroot}%{_sysconfdir}/magnum
install -m 644 etc/magnum/* %{buildroot}%{_sysconfdir}/magnum

install -p -D -m 755 %{SOURCE1} %{buildroot}%{_unitdir}/openstack-magnum-api.service
install -p -D -m 755 %{SOURCE2} %{buildroot}%{_unitdir}/openstack-magnum-conductor.service

mkdir -p %{buildroot}/var/log/magnum/
mkdir -p %{buildroot}/var/run/magnum/
%endif

%__rm -rf %{buildroot}%{py_sitelib}/{doc,tools}

%clean
%__rm -rf %{buildroot}

%pre
getent group magnum >/dev/null || groupadd -r magnum
getent passwd magnum >/dev/null || \
useradd -r -g magnum -d %{_sharedstatedir}/magnum -s /sbin/nologin \
-c "OpenStack Magnum Daemon" magnum

%post
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{daemon_prefix}.service
fi

%preun
/usr/bin/systemctl --no-reload disable %{daemon_prefix}.service > /dev/null 2>&1 || :
/usr/bin/systemctl stop %{daemon_prefix}.service > /dev/null 2>&1 || :

%files
%license LICENSE
%defattr(-,root,root,-)
%doc README* LICENSE* HACKING* ChangeLog AUTHORS
%{_usr}/bin/*

%if ! 0%{?usr_only}
%configfile %attr(0640, root, magnum) %{_sysconfdir}/magnum/*
%dir %attr(0755, magnum, nobody) %{_localstatedir}/log/magnum
%dir %attr(0755, magnum, nobody) %{_localstatedir}/run/magnum

%{_unitdir}/*
%endif

%files -n python-%{servicename}
%{python_sitelib}/%{modulename}
%{python_sitelib}/%{modulename}-%{version}-py%{python2_version}.egg-info
%exclude %{python_sitelib}/%{modulename}/tests


%files -n python-%{servicename}-tests
%{python_sitelib}/%{modulename}/tests


%changelog
