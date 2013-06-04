%global python_name quantum
%global daemon_prefix openstack-quantum

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

Name:		openstack-quantum
Version:        $version
Release:        1%{?dist}
Epoch:          $epoch
Summary:	Virtual network service for OpenStack (quantum)

Group:		Applications/System
License:	ASL 2.0
URL:		http://launchpad.net/quantum/

Source0:        %{python_name}-%{version}.tar.gz
Source1:	quantum.logrotate
Source2:	quantum-sudoers

Source10:	quantum-server.init
Source11:	quantum-linuxbridge-agent.init
Source12:	quantum-openvswitch-agent.init
Source13:	quantum-ryu-agent.init
Source14:	quantum-nec-agent.init
Source15:	quantum-dhcp-agent.init
Source16:	quantum-l3-agent.init
Source17:	quantum-ovs-cleanup.init
Source18:	quantum-hyperv-agent.init
Source19:	quantum-rpc-zmq-receiver.init

BuildArch:	noarch

BuildRequires:	python2-devel
BuildRequires:	python-setuptools
# Build require these parallel versions
# as setup.py build imports quantum.openstack.common.setup
# which will then check for these
BuildRequires:	python-sqlalchemy
BuildRequires:	python-webob
BuildRequires:	python-paste-deploy
BuildRequires:	python-routes
BuildRequires:	dos2unix

Requires:	python-quantum = %{epoch}:%{version}-%{release}
Requires:       python-keystone

Requires(post):   chkconfig
Requires(postun): initscripts
Requires(preun):  chkconfig
Requires(preun):  initscripts
Requires(pre):    shadow-utils


%description
Quantum is a virtual network service for Openstack. Just like
OpenStack Nova provides an API to dynamically request and configure
virtual servers, Quantum provides an API to dynamically request and
configure virtual networks. These networks connect "interfaces" from
other OpenStack services (e.g., virtual NICs from Nova VMs). The
Quantum API supports extensions to provide advanced network
capabilities (e.g., QoS, ACLs, network monitoring, etc.)


%package -n python-quantum
Summary:	Quantum Python libraries
Group:		Applications/System

#for $i in $requires
${i}
#end for
Requires:	sudo



%description -n python-quantum
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum Python library.


%package -n openstack-quantum-bigswitch
Summary:	Quantum Big Switch plugin
Group:		Applications/System

Requires:	openstack-quantum = %{version}-%{release}


%description -n openstack-quantum-bigswitch
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using the FloodLight Openflow Controller or the Big Switch
Networks Controller.


%package -n openstack-quantum-brocade
Summary:	Quantum Brocade plugin
Group:		Applications/System

Requires:	openstack-quantum = %{version}-%{release}


%description -n openstack-quantum-brocade
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using Brocade VCS switches running NOS.


%package -n openstack-quantum-cisco
Summary:	Quantum Cisco plugin
Group:		Applications/System

Requires:	openstack-quantum = %{version}-%{release}
Requires:	python-configobj


%description -n openstack-quantum-cisco
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using Cisco UCS and Nexus.


%package -n openstack-quantum-hyperv
Summary:	Quantum Hyper-V plugin
Group:		Applications/System

Requires:	openstack-quantum = %{version}-%{release}


%description -n openstack-quantum-hyperv
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using Microsoft Hyper-V.


%package -n openstack-quantum-linuxbridge
Summary:	Quantum linuxbridge plugin
Group:		Applications/System

Requires:	bridge-utils
Requires:	openstack-quantum = %{version}-%{release}
Requires:	python-pyudev


%description -n openstack-quantum-linuxbridge
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks as VLANs using Linux bridging.


%package -n openstack-quantum-midonet
Summary:	Quantum MidoNet plugin
Group:		Applications/System

Requires:	openstack-quantum = %{version}-%{release}


%description -n openstack-quantum-midonet
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using MidoNet from Midokura.


%package -n openstack-quantum-nicira
Summary:	Quantum Nicira plugin
Group:		Applications/System

Requires:	openstack-quantum = %{version}-%{release}


%description -n openstack-quantum-nicira
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using Nicira NVP.


%package -n openstack-quantum-openvswitch
Summary:	Quantum openvswitch plugin
Group:		Applications/System

Requires:	openstack-quantum = %{version}-%{release}
Requires:	openvswitch


%description -n openstack-quantum-openvswitch
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using Open vSwitch.


%package -n openstack-quantum-plumgrid
Summary:	Quantum PLUMgrid plugin
Group:		Applications/System

Requires:	openstack-quantum = %{version}-%{release}


%description -n openstack-quantum-plumgrid
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using the PLUMgrid platform.


%package -n openstack-quantum-ryu
Summary:	Quantum Ryu plugin
Group:		Applications/System

Requires:	openstack-quantum = %{version}-%{release}


%description -n openstack-quantum-ryu
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using the Ryu Network Operating System.


%package -n openstack-quantum-nec
Summary:	Quantum NEC plugin
Group:		Applications/System

Requires:	openstack-quantum = %{version}-%{release}


%description -n openstack-quantum-nec
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using the NEC OpenFlow controller.


%package -n openstack-quantum-metaplugin
Summary:	Quantum meta plugin
Group:		Applications/System

Requires:	openstack-quantum = %{version}-%{release}


%description -n openstack-quantum-metaplugin
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using multiple other quantum plugins.

#raw
%prep
%setup -q -n quantum-%{version}

find quantum -name \*.py -exec sed -i '/\/usr\/bin\/env python/d' {} \;

chmod 644 quantum/plugins/cisco/README

# Adjust configuration file content
sed -i 's/debug = True/debug = False/' etc/quantum.conf
sed -i 's/\# auth_strategy = keystone/auth_strategy = keystone/' etc/quantum.conf

# Remove unneeded dependency
sed -i '/setuptools_git/d' setup.py

# let RPM handle deps
sed -i '/setup_requires/d; /install_requires/d; /dependency_links/d' setup.py


%build
%{__python} setup.py build


%install
rm -rf %{buildroot}
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

# Remove unused files
rm -rf %{buildroot}%{python_sitelib}/bin
rm -rf %{buildroot}%{python_sitelib}/doc
rm -rf %{buildroot}%{python_sitelib}/tools
rm -rf %{buildroot}%{python_sitelib}/quantum/tests
rm -rf %{buildroot}%{python_sitelib}/quantum/plugins/*/tests
rm -f %{buildroot}%{python_sitelib}/quantum/plugins/*/run_tests.*
rm %{buildroot}/usr/etc/init.d/quantum-server

# Install execs
install -p -D -m 755 bin/quantum-* %{buildroot}%{_bindir}/

# Move rootwrap files to proper location
install -d -m 755 %{buildroot}%{_datarootdir}/quantum/rootwrap
mv %{buildroot}/usr/etc/quantum/rootwrap.d/*.filters %{buildroot}%{_datarootdir}/quantum/rootwrap

# Move config files to proper location
install -d -m 755 %{buildroot}%{_sysconfdir}/quantum
mv %{buildroot}/usr/etc/quantum/* %{buildroot}%{_sysconfdir}/quantum
chmod 640  %{buildroot}%{_sysconfdir}/quantum/plugins/*/*.ini

# Configure agents to use quantum-rootwrap
for f in %{buildroot}%{_sysconfdir}/quantum/plugins/*/*.ini %{buildroot}%{_sysconfdir}/quantum/*_agent.ini; do
    sed -i 's/^root_helper.*/root_helper = sudo quantum-rootwrap \/etc\/quantum\/rootwrap.conf/g' $f
done

# Configure quantum-dhcp-agent state_path
sed -i 's/state_path = \/opt\/stack\/data/state_path = \/var\/lib\/quantum/' %{buildroot}%{_sysconfdir}/quantum/dhcp_agent.ini

# Install logrotate
install -p -D -m 644 %{SOURCE1} %{buildroot}%{_sysconfdir}/logrotate.d/openstack-quantum

# Install sudoers
install -p -D -m 440 %{SOURCE2} %{buildroot}%{_sysconfdir}/sudoers.d/quantum

# Install sysv init scripts
install -p -D -m 755 %{SOURCE10} %{buildroot}%{_initrddir}/quantum-server
install -p -D -m 755 %{SOURCE11} %{buildroot}%{_initrddir}/quantum-linuxbridge-agent
install -p -D -m 755 %{SOURCE12} %{buildroot}%{_initrddir}/quantum-openvswitch-agent
install -p -D -m 755 %{SOURCE13} %{buildroot}%{_initrddir}/quantum-ryu-agent
install -p -D -m 755 %{SOURCE14} %{buildroot}%{_initrddir}/quantum-nec-agent
install -p -D -m 755 %{SOURCE15} %{buildroot}%{_initrddir}/quantum-dhcp-agent
install -p -D -m 755 %{SOURCE16} %{buildroot}%{_initrddir}/quantum-l3-agent
install -p -D -m 755 %{SOURCE17} %{buildroot}%{_initrddir}/quantum-ovs-cleanup
install -p -D -m 755 %{SOURCE18} %{buildroot}%{_initrddir}/quantum-hyperv-agent
install -p -D -m 755 %{SOURCE19} %{buildroot}%{_initrddir}/quantum-rpc-zmq-receiver

# Setup directories
install -d -m 755 %{buildroot}%{_datadir}/quantum
install -d -m 755 %{buildroot}%{_sharedstatedir}/quantum
install -d -m 755 %{buildroot}%{_localstatedir}/log/quantum
install -d -m 755 %{buildroot}%{_localstatedir}/run/quantum

# Install version info file
cat > %{buildroot}%{_sysconfdir}/quantum/release <<EOF
[Quantum]
vendor = OpenStack LLC
product = OpenStack Quantum
package = %{release}
EOF

%clean
rm -rf %{buildroot}


%pre
getent group quantum >/dev/null || groupadd -r quantum --gid 164
getent passwd quantum >/dev/null || \
    useradd --uid 164 -r -g quantum -d %{_sharedstatedir}/quantum -s /sbin/nologin \
    -c "OpenStack Quantum Daemons" quantum
exit 0

%post
if [ $1 -eq 1 ] ; then
    # Initial installation
    /sbin/chkconfig --add quantum-server
fi

%preun
if [ $1 -eq 0 ] ; then
    # Package removal, not upgrade
    /sbin/service quantum-server stop >/dev/null 2>&1
    /sbin/chkconfig --del quantum-server
    /sbin/service quantum-dhcp-agent stop >/dev/null 2>&1
    /sbin/chkconfig --del quantum-dhcp-agent
    /sbin/service quantum-l3-agent stop >/dev/null 2>&1
    /sbin/chkconfig --del quantum-l3-agent
fi

%postun
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    /sbin/service quantum-server condrestart >/dev/null 2>&1 || :
fi


%post -n openstack-quantum-linuxbridge
if [ $1 -eq 1 ] ; then
    # Initial installation
    /sbin/chkconfig --add quantum-linuxbridge-agent
fi

%preun -n openstack-quantum-linuxbridge
if [ $1 -eq 0 ] ; then
    # Package removal, not upgrade
    /sbin/service quantum-linuxbridge-agent stop >/dev/null 2>&1
    /sbin/chkconfig --del quantum-linuxbridge-agent
fi

%postun -n openstack-quantum-linuxbridge
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    /sbin/service quantum-linuxbridge-agent condrestart >/dev/null 2>&1 || :
fi


%post -n openstack-quantum-openvswitch
if [ $1 -eq 1 ] ; then
    # Initial installation
    /sbin/chkconfig --add quantum-openvswitch-agent
    /sbin/chkconfig --add quantum-ovs-cleanup
fi

%preun -n openstack-quantum-openvswitch
if [ $1 -eq 0 ] ; then
    # Package removal, not upgrade
    /sbin/service quantum-openvswitch-agent stop >/dev/null 2>&1
    /sbin/chkconfig --del quantum-openvswitch-agent
    /sbin/service quantum-ovs-cleanup stop >/dev/null 2>&1
    /sbin/chkconfig --del quantum-ovs-cleanup
fi

%postun -n openstack-quantum-openvswitch
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    /sbin/service quantum-openvswitch-agent condrestart >/dev/null 2>&1 || :
fi


%post -n openstack-quantum-ryu
if [ $1 -eq 1 ] ; then
    # Initial installation
    /sbin/chkconfig --add quantum-ryu-agent
fi

%preun -n openstack-quantum-ryu
if [ $1 -eq 0 ] ; then
    # Package removal, not upgrade
    /sbin/service quantum-ryu-agent stop >/dev/null 2>&1
    /sbin/chkconfig --del quantum-ryu-agent
fi

%postun -n openstack-quantum-ryu
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    /sbin/service quantum-ryu-agent condrestart >/dev/null 2>&1 || :
fi


%preun -n openstack-quantum-nec
if [ $1 -eq 0 ] ; then
    # Package removal, not upgrade
    /sbin/service quantum-nec-agent stop >/dev/null 2>&1
    /sbin/chkconfig --del quantum-nec-agent
fi


%postun -n openstack-quantum-nec
/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    /sbin/service quantum-nec-agent condrestart >/dev/null 2>&1 || :
fi


%files
%doc LICENSE
%doc README
%{_bindir}/quantum-db-manage
%{_bindir}/quantum-debug
%{_bindir}/quantum-dhcp-agent
%{_bindir}/quantum-dhcp-agent-dnsmasq-lease-update
%{_bindir}/quantum-l3-agent
%{_bindir}/quantum-lbaas-agent
%{_bindir}/quantum-metadata-agent
%{_bindir}/quantum-netns-cleanup
%{_bindir}/quantum-ns-metadata-proxy
%{_bindir}/quantum-rootwrap
%{_bindir}/quantum-rpc-zmq-receiver
%{_bindir}/quantum-server
%{_bindir}/quantum-usage-audit
%{_initrddir}/quantum-server
%{_initrddir}/quantum-dhcp-agent
%{_initrddir}/quantum-l3-agent
%{_initrddir}/quantum-rpc-zmq-receiver
%dir %{_sysconfdir}/quantum
%{_sysconfdir}/quantum/release
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/api-paste.ini
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/dhcp_agent.ini
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/l3_agent.ini
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/metadata_agent.ini
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/lbaas_agent.ini
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/policy.json
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/quantum.conf
%config(noreplace) %{_sysconfdir}/quantum/rootwrap.conf
%dir %{_sysconfdir}/quantum/plugins
%config(noreplace) %{_sysconfdir}/logrotate.d/*
%config(noreplace) %{_sysconfdir}/sudoers.d/quantum
%dir %attr(0755, quantum, quantum) %{_sharedstatedir}/quantum
%dir %attr(0755, quantum, quantum) %{_localstatedir}/log/quantum
%dir %{_datarootdir}/quantum
%dir %{_datarootdir}/quantum/rootwrap
%{_datarootdir}/quantum/rootwrap/dhcp.filters
%{_datarootdir}/quantum/rootwrap/iptables-firewall.filters
%{_datarootdir}/quantum/rootwrap/l3.filters
%{_datarootdir}/quantum/rootwrap/lbaas-haproxy.filters


%files -n python-quantum
%doc LICENSE
%doc README
%{python_sitelib}/quantum
%exclude %{python_sitelib}/quantum/plugins/cisco/extensions/_credential_view.py*
%exclude %{python_sitelib}/quantum/plugins/cisco/extensions/credential.py*
%exclude %{python_sitelib}/quantum/plugins/cisco/extensions/qos.py*
%exclude %{python_sitelib}/quantum/plugins/cisco/extensions/_qos_view.py*
%exclude %{python_sitelib}/quantum/plugins/bigswitch
%exclude %{python_sitelib}/quantum/plugins/brocade
%exclude %{python_sitelib}/quantum/plugins/cisco
%exclude %{python_sitelib}/quantum/plugins/hyperv
%exclude %{python_sitelib}/quantum/plugins/linuxbridge
%exclude %{python_sitelib}/quantum/plugins/metaplugin
%exclude %{python_sitelib}/quantum/plugins/midonet
%exclude %{python_sitelib}/quantum/plugins/nec
%exclude %{python_sitelib}/quantum/plugins/nicira
%exclude %{python_sitelib}/quantum/plugins/openvswitch
%exclude %{python_sitelib}/quantum/plugins/plumgrid
%exclude %{python_sitelib}/quantum/plugins/ryu
%{python_sitelib}/quantum-%%{version}-*.egg-info


%files -n openstack-quantum-bigswitch
%doc LICENSE
%doc quantum/plugins/bigswitch/README
%{python_sitelib}/quantum/plugins/bigswitch
%dir %{_sysconfdir}/quantum/plugins/bigswitch
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/bigswitch/*.ini


%files -n openstack-quantum-brocade
%doc LICENSE
%doc quantum/plugins/brocade/README.md
%{python_sitelib}/quantum/plugins/brocade
%dir %{_sysconfdir}/quantum/plugins/brocade
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/brocade/*.ini


%files -n openstack-quantum-cisco
%doc LICENSE
%doc quantum/plugins/cisco/README
%{python_sitelib}/quantum/plugins/cisco/extensions/_credential_view.py*
%{python_sitelib}/quantum/plugins/cisco/extensions/credential.py*
%{python_sitelib}/quantum/plugins/cisco/extensions/qos.py*
%{python_sitelib}/quantum/plugins/cisco/extensions/_qos_view.py*
%{python_sitelib}/quantum/plugins/cisco
%dir %{_sysconfdir}/quantum/plugins/cisco
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/cisco/*.ini


%files -n openstack-quantum-hyperv
%doc LICENSE
#%%doc quantum/plugins/hyperv/README
%{_bindir}/quantum-hyperv-agent
%{_initrddir}/quantum-hyperv-agent
%{python_sitelib}/quantum/plugins/hyperv
%dir %{_sysconfdir}/quantum/plugins/hyperv
%exclude %{python_sitelib}/quantum/plugins/hyperv/agent
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/hyperv/*.ini


%files -n openstack-quantum-linuxbridge
%doc LICENSE
%doc quantum/plugins/linuxbridge/README
%{_bindir}/quantum-linuxbridge-agent
%{_initrddir}/quantum-linuxbridge-agent
%{python_sitelib}/quantum/plugins/linuxbridge
%{_datarootdir}/quantum/rootwrap/linuxbridge-plugin.filters
%dir %{_sysconfdir}/quantum/plugins/linuxbridge
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/linuxbridge/*.ini


%files -n openstack-quantum-midonet
%doc LICENSE
#%%doc quantum/plugins/midonet/README
%{python_sitelib}/quantum/plugins/midonet
%dir %{_sysconfdir}/quantum/plugins/midonet
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/midonet/*.ini


%files -n openstack-quantum-nicira
%doc LICENSE
%doc quantum/plugins/nicira/nicira_nvp_plugin/README
%{_bindir}/quantum-check-nvp-config
%{python_sitelib}/quantum/plugins/nicira
%dir %{_sysconfdir}/quantum/plugins/nicira
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/nicira/*.ini


%files -n openstack-quantum-openvswitch
%doc LICENSE
%doc quantum/plugins/openvswitch/README
%{_bindir}/quantum-openvswitch-agent
%{_bindir}/quantum-ovs-cleanup
%{_initrddir}/quantum-openvswitch-agent
%{_initrddir}/quantum-ovs-cleanup
%{python_sitelib}/quantum/plugins/openvswitch
%{_datarootdir}/quantum/rootwrap/openvswitch-plugin.filters
%dir %{_sysconfdir}/quantum/plugins/openvswitch
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/openvswitch/*.ini


%files -n openstack-quantum-plumgrid
%doc LICENSE
%doc quantum/plugins/plumgrid/README
%{python_sitelib}/quantum/plugins/plumgrid
%dir %{_sysconfdir}/quantum/plugins/plumgrid
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/plumgrid/*.ini


%files -n openstack-quantum-ryu
%doc LICENSE
%doc quantum/plugins/ryu/README
%{_bindir}/quantum-ryu-agent
%{_initrddir}/quantum-ryu-agent
%{python_sitelib}/quantum/plugins/ryu
%{_datarootdir}/quantum/rootwrap/ryu-plugin.filters
%dir %{_sysconfdir}/quantum/plugins/ryu
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/ryu/*.ini


%files -n openstack-quantum-nec
%doc LICENSE
%doc quantum/plugins/nec/README
%{_bindir}/quantum-nec-agent
%{_initrddir}/quantum-nec-agent
%{python_sitelib}/quantum/plugins/nec
%{_datarootdir}/quantum/rootwrap/nec-plugin.filters
%dir %{_sysconfdir}/quantum/plugins/nec
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/nec/*.ini


%files -n openstack-quantum-metaplugin
%doc LICENSE
%doc quantum/plugins/metaplugin/README
%{python_sitelib}/quantum/plugins/metaplugin
%dir %{_sysconfdir}/quantum/plugins/metaplugin
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/metaplugin/*.ini

%changelog
#end raw
