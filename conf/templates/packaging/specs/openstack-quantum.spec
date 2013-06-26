#encoding UTF-8
# Based on spec by:
# * Terry Wilson <twilson@redhat.com>
# * Alan Pevec <apevec@redhat.com>
# * Martin Magr <mmagr@redhat.com>
# * Gary Kotton <gkotton@redhat.com>
# * Robert Kukura <rkukura@redhat.com>
# * Pádraig Brady <P@draigBrady.com>


%global python_name quantum
%global daemon_prefix openstack-quantum
%global os_version $version

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

Name:		openstack-quantum
Version:        %{os_version}$version_suffix
Release:        $release%{?dist}
Epoch:          $epoch
Summary:	Virtual network service for OpenStack (quantum)

Group:		Applications/System
License:	ASL 2.0
URL:		http://launchpad.net/quantum/

Source0:        %{python_name}-%{os_version}.tar.gz
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

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

BuildArch:	noarch

BuildRequires:	python-devel
BuildRequires:	python-setuptools
# Build require these parallel versions
# as setup.py build imports quantum.openstack.common.setup
# which will then check for these
# BuildRequires:	python-sqlalchemy
# BuildRequires:	python-webob
# BuildRequires:	python-paste-deploy
# BuildRequires:	python-routes
BuildRequires:	dos2unix

Requires:	python-quantum = %{epoch}:%{version}-%{release}
Requires:       python-keystone

%if ! 0%{?usr_only}
Requires(post):   chkconfig
Requires(postun): initscripts
Requires(preun):  chkconfig
Requires(preun):  initscripts
Requires(pre):    shadow-utils
%endif

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

Requires:	sudo
#for $i in $requires
Requires:	${i}
#end for


%description -n python-quantum
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum Python library.


%package -n openstack-quantum-bigswitch
Summary:	Quantum Big Switch plugin
Group:		Applications/System

Requires:	openstack-quantum = %{epoch}:%{version}-%{release}


%description -n openstack-quantum-bigswitch
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using the FloodLight Openflow Controller or the Big Switch
Networks Controller.


%package -n openstack-quantum-brocade
Summary:	Quantum Brocade plugin
Group:		Applications/System

Requires:	openstack-quantum = %{epoch}:%{version}-%{release}


%description -n openstack-quantum-brocade
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using Brocade VCS switches running NOS.


%package -n openstack-quantum-cisco
Summary:	Quantum Cisco plugin
Group:		Applications/System

Requires:	openstack-quantum = %{epoch}:%{version}-%{release}
Requires:	python-configobj


%description -n openstack-quantum-cisco
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using Cisco UCS and Nexus.


%package -n openstack-quantum-hyperv
Summary:	Quantum Hyper-V plugin
Group:		Applications/System

Requires:	openstack-quantum = %{epoch}:%{version}-%{release}


%description -n openstack-quantum-hyperv
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using Microsoft Hyper-V.


%package -n openstack-quantum-linuxbridge
Summary:	Quantum linuxbridge plugin
Group:		Applications/System

Requires:	bridge-utils
Requires:	openstack-quantum = %{epoch}:%{version}-%{release}
Requires:	python-pyudev


%description -n openstack-quantum-linuxbridge
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks as VLANs using Linux bridging.


%package -n openstack-quantum-midonet
Summary:	Quantum MidoNet plugin
Group:		Applications/System

Requires:	openstack-quantum = %{epoch}:%{version}-%{release}


%description -n openstack-quantum-midonet
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using MidoNet from Midokura.


%package -n openstack-quantum-nicira
Summary:	Quantum Nicira plugin
Group:		Applications/System

Requires:	openstack-quantum = %{epoch}:%{version}-%{release}


%description -n openstack-quantum-nicira
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using Nicira NVP.


%package -n openstack-quantum-openvswitch
Summary:	Quantum openvswitch plugin
Group:		Applications/System

Requires:	openstack-quantum = %{epoch}:%{version}-%{release}
Requires:	openvswitch


%description -n openstack-quantum-openvswitch
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using Open vSwitch.


%package -n openstack-quantum-plumgrid
Summary:	Quantum PLUMgrid plugin
Group:		Applications/System

Requires:	openstack-quantum = %{epoch}:%{version}-%{release}


%description -n openstack-quantum-plumgrid
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using the PLUMgrid platform.


%package -n openstack-quantum-ryu
Summary:	Quantum Ryu plugin
Group:		Applications/System

Requires:	openstack-quantum = %{epoch}:%{version}-%{release}


%description -n openstack-quantum-ryu
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using the Ryu Network Operating System.


%package -n openstack-quantum-nec
Summary:	Quantum NEC plugin
Group:		Applications/System

Requires:	openstack-quantum = %{epoch}:%{version}-%{release}


%description -n openstack-quantum-nec
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using the NEC OpenFlow controller.


%package -n openstack-quantum-metaplugin
Summary:	Quantum meta plugin
Group:		Applications/System

Requires:	openstack-quantum = %{epoch}:%{version}-%{release}


%description -n openstack-quantum-metaplugin
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains the quantum plugin that implements virtual
networks using multiple other quantum plugins.


%if ! 0%{?no_tests}
%package -n python-%{python_name}-tests
Summary:          Tests for Quantum
Group:            Development/Libraries

Requires:         %{name} = %{epoch}:%{version}-%{release}
Requires:         %{name}-bigswitch = %{epoch}:%{version}-%{release}
Requires:         %{name}-brocade = %{epoch}:%{version}-%{release}
Requires:         %{name}-cisco = %{epoch}:%{version}-%{release}
Requires:         %{name}-hyperv = %{epoch}:%{version}-%{release}
Requires:         %{name}-linuxbridge = %{epoch}:%{version}-%{release}
Requires:         %{name}-midonet = %{epoch}:%{version}-%{release}
Requires:         %{name}-nicira = %{epoch}:%{version}-%{release}
Requires:         %{name}-openvswitch = %{epoch}:%{version}-%{release}
Requires:         %{name}-plumgrid = %{epoch}:%{version}-%{release}
Requires:         %{name}-ryu = %{epoch}:%{version}-%{release}
Requires:         %{name}-nec = %{epoch}:%{version}-%{release}
Requires:         %{name}-metaplugin = %{epoch}:%{version}-%{release}
Requires:         python-%{python_name} = %{epoch}:%{version}-%{release}

Requires:         python-nose
Requires:         python-openstack-nose-plugin
Requires:         python-nose-exclude

#for $i in $test_requires
Requires:         ${i}
#end for

%description -n python-%{python_name}-tests
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains unit and functional tests for Quantum, with
simple runner (%{python_name}-run-unit-tests).
%endif

%prep
%setup -q -n quantum-%{os_version}
#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for
#raw

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

%if ! 0%{?no_tests}
# Make simple test runner
cat > %{buildroot}%{_bindir}/%{python_name}-run-unit-tests << EOF
#!/bin/bash
export NOSE_WITH_OPENSTACK=1
export NOSE_OPENSTACK_RED=0.05
export NOSE_OPENSTACK_YELLOW=0.025
export NOSE_OPENSTACK_SHOW_ELAPSED=1

cd %{python_sitelib}
exec nosetests --openstack-color --verbosity=2 --detailed-errors \
#end raw
#for i in $exclude_tests
    --exclude "${i}" \\
#end for
#raw
    %{python_name}/tests "\$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/%{python_name}-run-unit-tests
%endif

# Remove unused files
rm -rf %{buildroot}%{python_sitelib}/bin
rm -rf %{buildroot}%{python_sitelib}/doc
rm -rf %{buildroot}%{python_sitelib}/tools
rm -f %{buildroot}%{python_sitelib}/quantum/plugins/*/run_tests.*
rm %{buildroot}/usr/etc/init.d/quantum-server

# Install execs
install -p -D -m 755 bin/quantum-* %{buildroot}%{_bindir}/

# Move rootwrap files to proper location
install -d -m 755 %{buildroot}%{_datarootdir}/quantum/rootwrap
mv %{buildroot}/usr/etc/quantum/rootwrap.d/*.filters %{buildroot}%{_datarootdir}/quantum/rootwrap

%if ! 0%{?usr_only}
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
install -p -D -m 755 %{SOURCE10} %{buildroot}%{_initrddir}/%{daemon_prefix}-server
install -p -D -m 755 %{SOURCE11} %{buildroot}%{_initrddir}/%{daemon_prefix}-linuxbridge-agent
install -p -D -m 755 %{SOURCE12} %{buildroot}%{_initrddir}/%{daemon_prefix}-openvswitch-agent
install -p -D -m 755 %{SOURCE13} %{buildroot}%{_initrddir}/%{daemon_prefix}-ryu-agent
install -p -D -m 755 %{SOURCE14} %{buildroot}%{_initrddir}/%{daemon_prefix}-nec-agent
install -p -D -m 755 %{SOURCE15} %{buildroot}%{_initrddir}/%{daemon_prefix}-dhcp-agent
install -p -D -m 755 %{SOURCE16} %{buildroot}%{_initrddir}/%{daemon_prefix}-l3-agent
install -p -D -m 755 %{SOURCE17} %{buildroot}%{_initrddir}/%{daemon_prefix}-ovs-cleanup
install -p -D -m 755 %{SOURCE18} %{buildroot}%{_initrddir}/%{daemon_prefix}-hyperv-agent
install -p -D -m 755 %{SOURCE19} %{buildroot}%{_initrddir}/%{daemon_prefix}-rpc-zmq-receiver

# Setup directories
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
%else
rm -rf %{buildroot}/usr/etc/
%endif

%clean
rm -rf %{buildroot}


%if ! 0%{?usr_only}
%pre
getent group quantum >/dev/null || groupadd -r quantum
getent passwd quantum >/dev/null || \
useradd -r -g quantum -d %{_sharedstatedir}/quantum -s /sbin/nologin \
-c "OpenStack Quantum Daemons" quantum
exit 0

# Do not autostart daemons in %post since they are not configured yet
#end raw

#set $daemon_map = {"": ["server", "dhcp-agent", "l3-agent"], "linuxbridge": ["linuxbridge-agent"], "openvswitch": ["openvswitch-agent", "ovs-cleanup"], "ryu": ["ryu-agent"], "nec": ["nec-agent"]}
#for $key, $value in $daemon_map.iteritems()
#set $daemon_list = " ".join($value) if $value else $key
%preun $key
if [ \$1 -eq 0 ] ; then
    for svc in $daemon_list; do
        /sbin/service %{daemon_prefix}-\${svc} stop &>/dev/null
        /sbin/chkconfig --del %{daemon_prefix}-\${svc}
    done
    exit 0
fi

%postun $key
if [ \$1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    for svc in $daemon_list; do
        /sbin/service %{daemon_prefix}-\${svc} condrestart &>/dev/null
    done
    exit 0
fi

#end for
%endif
#raw

%files
%doc README* LICENSE* HACKING* ChangeLog AUTHORS
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
%dir %{_datarootdir}/quantum
%dir %{_datarootdir}/quantum/rootwrap
%{_datarootdir}/quantum/rootwrap/dhcp.filters
%{_datarootdir}/quantum/rootwrap/iptables-firewall.filters
%{_datarootdir}/quantum/rootwrap/l3.filters
%{_datarootdir}/quantum/rootwrap/lbaas-haproxy.filters
%if ! 0%{?usr_only}
%{_initrddir}/%{daemon_prefix}-server
%{_initrddir}/%{daemon_prefix}-dhcp-agent
%{_initrddir}/%{daemon_prefix}-l3-agent
%{_initrddir}/%{daemon_prefix}-rpc-zmq-receiver
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
%dir %attr(0755, quantum, quantum) %{_localstatedir}/run/quantum
%endif

%files -n python-quantum
%doc LICENSE
%doc README
%{python_sitelib}/quantum
%exclude %{python_sitelib}/quantum/tests
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
%{python_sitelib}/quantum-*.egg-info


%files -n openstack-quantum-bigswitch
%doc LICENSE
%doc quantum/plugins/bigswitch/README
%{python_sitelib}/quantum/plugins/bigswitch
%exclude %{python_sitelib}/quantum/plugins/bigswitch/tests

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/quantum/plugins/bigswitch
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/bigswitch/*.ini
%endif


%files -n openstack-quantum-brocade
%doc LICENSE
%doc quantum/plugins/brocade/README.md
%{python_sitelib}/quantum/plugins/brocade
%exclude %{python_sitelib}/quantum/plugins/brocade/tests

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/quantum/plugins/brocade
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/brocade/*.ini
%endif


%files -n openstack-quantum-cisco
%doc LICENSE
%doc quantum/plugins/cisco/README
%{python_sitelib}/quantum/plugins/cisco
%exclude %{python_sitelib}/quantum/plugins/cisco/tests

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/quantum/plugins/cisco
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/cisco/*.ini
%endif


%files -n openstack-quantum-hyperv
%doc LICENSE
#%%doc quantum/plugins/hyperv/README
%{_bindir}/quantum-hyperv-agent
%{python_sitelib}/quantum/plugins/hyperv
%exclude %{python_sitelib}/quantum/plugins/hyperv/agent

%if ! 0%{?usr_only}
%{_initrddir}/%{daemon_prefix}-hyperv-agent
%dir %{_sysconfdir}/quantum/plugins/hyperv
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/hyperv/*.ini
%endif


%files -n openstack-quantum-linuxbridge
%doc LICENSE
%doc quantum/plugins/linuxbridge/README
%{_bindir}/quantum-linuxbridge-agent
%{python_sitelib}/quantum/plugins/linuxbridge
%{_datarootdir}/quantum/rootwrap/linuxbridge-plugin.filters

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/quantum/plugins/linuxbridge
%{_initrddir}/%{daemon_prefix}-linuxbridge-agent
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/linuxbridge/*.ini
%endif


%files -n openstack-quantum-midonet
%doc LICENSE
#%%doc quantum/plugins/midonet/README
%{python_sitelib}/quantum/plugins/midonet

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/quantum/plugins/midonet
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/midonet/*.ini
%endif


%files -n openstack-quantum-nicira
%doc LICENSE
%doc quantum/plugins/nicira/nicira_nvp_plugin/README
%{_bindir}/quantum-check-nvp-config
%{python_sitelib}/quantum/plugins/nicira

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/quantum/plugins/nicira
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/nicira/*.ini
%endif


%files -n openstack-quantum-openvswitch
%doc LICENSE
%doc quantum/plugins/openvswitch/README
%{_bindir}/quantum-openvswitch-agent
%{_bindir}/quantum-ovs-cleanup
%{_datarootdir}/quantum/rootwrap/openvswitch-plugin.filters
%{python_sitelib}/quantum/plugins/openvswitch

%if ! 0%{?usr_only}
%{_initrddir}/%{daemon_prefix}-openvswitch-agent
%{_initrddir}/%{daemon_prefix}-ovs-cleanup
%dir %{_sysconfdir}/quantum/plugins/openvswitch
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/openvswitch/*.ini
%endif


%files -n openstack-quantum-plumgrid
%doc LICENSE
%doc quantum/plugins/plumgrid/README
%{python_sitelib}/quantum/plugins/plumgrid

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/quantum/plugins/plumgrid
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/plumgrid/*.ini
%endif


%files -n openstack-quantum-ryu
%doc LICENSE
%doc quantum/plugins/ryu/README
%{_bindir}/quantum-ryu-agent
%{python_sitelib}/quantum/plugins/ryu
%{_datarootdir}/quantum/rootwrap/ryu-plugin.filters

%if ! 0%{?usr_only}
%{_initrddir}/%{daemon_prefix}-ryu-agent
%dir %{_sysconfdir}/quantum/plugins/ryu
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/ryu/*.ini
%endif


%files -n openstack-quantum-nec
%doc LICENSE
%doc quantum/plugins/nec/README
%{_bindir}/quantum-nec-agent
%{python_sitelib}/quantum/plugins/nec
%{_datarootdir}/quantum/rootwrap/nec-plugin.filters

%if ! 0%{?usr_only}
%{_initrddir}/%{daemon_prefix}-nec-agent
%dir %{_sysconfdir}/quantum/plugins/nec
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/nec/*.ini
%endif


%files -n openstack-quantum-metaplugin
%doc LICENSE
%doc quantum/plugins/metaplugin/README
%{python_sitelib}/quantum/plugins/metaplugin

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/quantum/plugins/metaplugin
%config(noreplace) %attr(0640, root, quantum) %{_sysconfdir}/quantum/plugins/metaplugin/*.ini
%endif

%if ! 0%{?no_tests}
%files -n python-%{python_name}-tests
%{python_sitelib}/%{python_name}/tests
%exclude %{python_sitelib}/%{python_name}/tests/unit/hyperv/test_hyperv_quantum_agent.*
%{_bindir}/%{python_name}-run-unit-tests
%endif

%changelog
#end raw
