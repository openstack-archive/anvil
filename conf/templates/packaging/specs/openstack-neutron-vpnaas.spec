%global modulename neutron_vpnaas
%global servicename neutron-vpn
%global type VPNaaS
%global python_name neutron-vpnaas
%global daemon_prefix neutron-vpn
%global os_version ${version}
%global no_tests $no_tests
%global tests_data_dir %{_datarootdir}/%{python_name}-tests

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

Name:           openstack-%{python_name}
Version:        %{os_version}$version_suffix
Release:        $release%{?dist}
Epoch:          $epoch
Summary:        Openstack Networking %{type} plugin

License:        ASL 2.0
URL:            http://launchpad.net/neutron/
Source0:        %{python_name}-%{os_version}.tar.gz

%if ! (0%{?rhel} > 6)
Source10:         openstack-neutron-vpn-agent.init
%else
Source10:         openstack-neutron-vpn-agent.service
%endif

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

Obsoletes:      openstack-neutron-vpn-agent < %{version}
Provides:       openstack-neutron-vpn-agent = %{epoch}:%{version}-%{release}

BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}

BuildArch:      noarch
BuildRequires:  python2-devel
BuildRequires:  python-pbr
BuildRequires:  python-setuptools

Requires:       python-%{python_name} = %{epoch}:%{version}-%{release}
Requires:       openstack-neutron >= %{epoch}:%{version}-%{release}

%description
This is a %{type} service plugin for Openstack Neutron (Networking) service.


%package -n python-%{python_name}
Summary:        Neutron %{type} Python libraries
Group:          Applications/System

Requires:       python-neutron >= %{epoch}:%{version}-%{release}
#for $i in $requires
Requires:         ${i}
#end for

#for $i in $conflicts
Conflicts:       ${i}
#end for

%description -n python-%{python_name}
This is a %{type} service plugin for Openstack Neutron (Networking) service.

This package contains the Neutron %{type} Python library.


%package -n python-%{python_name}-tests
Summary:        Neutron %{type} tests
Group:          Applications/System

Requires:       python-%{python_name} = %{epoch}:%{version}-%{release}


%description -n python-%{python_name}-tests
This is a %{type} service plugin for Openstack Neutron (Networking) service.

This package contains Neutron %{type} test files.


%prep
%setup -q -n %{python_name}-%{os_version}

#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for

%build
#export PBR_VERSION=%{version}
#export SKIP_PIP_INSTALL=1
%{__python} setup.py build


%install
#export PBR_VERSION=%{version}
#export SKIP_PIP_INSTALL=1
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

# Move rootwrap files to proper location
install -d -m 755 %{buildroot}%{_datarootdir}/neutron/rootwrap
mv %{buildroot}/usr/etc/neutron/rootwrap.d/*.filters %{buildroot}%{_datarootdir}/neutron/rootwrap

%if ! 0%{?usr_only}
# Move config files to proper location
install -d -m 755 %{buildroot}%{_sysconfdir}/neutron
mv %{buildroot}/usr/etc/neutron/*.ini %{buildroot}%{_sysconfdir}/neutron
mv %{buildroot}/usr/etc/neutron/*.conf %{buildroot}%{_sysconfdir}/neutron

# Install init scripts
%if ! (0%{?rhel} > 6)
install -p -D -m 644 %{SOURCE10} %{buildroot}%{_initrddir}/openstack-%{servicename}-agent
%else
install -p -D -m 644 %{SOURCE10} %{buildroot}%{_unitdir}/openstack-%{servicename}-agent.service
%endif

# Create and populate distribution configuration directory for VPN agent
# (the same as for L3 agent)
mkdir -p %{buildroot}%{_datadir}/neutron/l3_agent
ln -s %{_sysconfdir}/neutron/vpn_agent.ini %{buildroot}%{_datadir}/neutron/l3_agent/vpn_agent.conf

# Create configuration directory that can be populated by users with custom *.conf files
mkdir -p %{buildroot}/%{_sysconfdir}/neutron/conf.d/neutron-vpn-agent

# Make sure neutron-server loads new configuration file
mkdir -p %{buildroot}/%{_datadir}/neutron/server
ln -s %{_sysconfdir}/neutron/%{modulename}.conf %{buildroot}%{_datadir}/neutron/server/%{modulename}.conf
%endif

%if ! 0%{?usr_only}
#set $daemon_map = {"": ["neutron-vpn-agent"]}
#for $key, $value in $daemon_map.iteritems()
#set $daemon_list = " ".join($value) if $value else $key
%if 0%{?rhel} > 6
%post $key
if [ \$1 -eq 1 ] ; then
    # Initial installation
    for svc in $daemon_list; do
        /usr/bin/systemctl preset openstack-\${svc}.service
    done
fi
%endif

%preun $key
if [ \$1 -eq 0 ] ; then
    for svc in $daemon_list; do
%if ! (0%{?rhel} > 6)
        /sbin/service openstack-\${svc} stop &>/dev/null
        /sbin/chkconfig --del openstack-\${svc}
%else
        /usr/bin/systemctl --no-reload disable openstack-\${svc}.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop openstack-\${svc}.service > /dev/null 2>&1 || :
%endif
    done
    exit 0
fi

#end for
%endif

%files
%license LICENSE
%doc AUTHORS CONTRIBUTING.rst README.rst
%{_bindir}/neutron-vpn-agent
%{_bindir}/neutron-vpn-netns-wrapper
%{_datarootdir}/neutron/rootwrap/vpnaas.filters

%if ! 0%{?usr_only}
%config(noreplace) %attr(0640, root, neutron) %{_sysconfdir}/neutron/vpn_agent.ini
%config(noreplace) %attr(0640, root, neutron) %{_sysconfdir}/neutron/neutron_vpnaas.conf
%dir %{_sysconfdir}/neutron/conf.d
%dir %{_sysconfdir}/neutron/conf.d/neutron-vpn-agent
%{_datadir}/neutron/l3_agent/*.conf
%{_datadir}/neutron/server/%{modulename}.conf

%if ! (0%{?rhel} > 6)
%{_initrddir}/openstack-neutron-vpn-agent
%else
%{_unitdir}/openstack-neutron-vpn-agent.service
%endif
%endif

%files -n python-%{python_name}
%{python_sitelib}/%{modulename}
%{python_sitelib}/%{modulename}-%{version}-py%{python2_version}.egg-info
%exclude %{python_sitelib}/%{modulename}/tests


%files -n python-%{python_name}-tests
%{python_sitelib}/%{modulename}/tests


%changelog
