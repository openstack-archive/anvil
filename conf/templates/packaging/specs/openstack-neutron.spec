#encoding UTF-8
# Based on spec by:
# * Terry Wilson <twilson@redhat.com>
# * Alan Pevec <apevec@redhat.com>
# * Martin Magr <mmagr@redhat.com>
# * Gary Kotton <gkotton@redhat.com>
# * Robert Kukura <rkukura@redhat.com>
# * Pádraig Brady <P@draigBrady.com>


%global python_name neutron
%global daemon_prefix openstack-neutron
%global os_version $version
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

Name:		openstack-neutron
Version:        %{os_version}$version_suffix
Release:        $release%{?dist}
Epoch:          $epoch
Summary:	Virtual network service for OpenStack (neutron)

Group:		Applications/System
License:	ASL 2.0
URL:		http://launchpad.net/neutron/

Source0:        %{python_name}-%{os_version}.tar.gz
Source1:	neutron.logrotate
Source2:	neutron-sudoers

%if ! (0%{?rhel} > 6)
Source10:	neutron-server.init
Source11:	neutron-linuxbridge-agent.init
Source12:	neutron-openvswitch-agent.init
#if $older_than('2015.1')
Source13:	neutron-ryu-agent.init
#end if
Source14:	neutron-nec-agent.init
Source15:	neutron-dhcp-agent.init
Source16:	neutron-l3-agent.init
Source17:	neutron-ovs-cleanup.init
#if $older_than('2015.1')
Source18:	neutron-hyperv-agent.init
#end if
#if $older_than('2014.2')
Source19:	neutron-rpc-zmq-receiver.init
#end if
Source20:	neutron-metadata-agent.init
#if $newer_than('2014.2')
#if $older_than('2015.1')
Source21:       neutron-lbaas-agent.init
#end if
Source22:       neutron-mlnx-agent.init
#if $older_than('2015.1')
Source23:       neutron-vpn-agent.init
#end if
Source24:       neutron-metering-agent.init
Source25:       neutron-sriov-nic-agent.init
#if $older_than('2015.1')
Source26:       neutron-cisco-cfg-agent.init
#end if
Source27:       neutron-netns-cleanup.init
#end if
%else
Source10:      neutron-server.service
Source11:      neutron-linuxbridge-agent.service
Source12:      neutron-openvswitch-agent.service
#if $older_than('2015.1')
Source13:      neutron-ryu-agent.service
#end if
Source14:      neutron-nec-agent.service
Source15:      neutron-dhcp-agent.service
Source16:      neutron-l3-agent.service
Source17:      neutron-ovs-cleanup.service
#if $older_than('2015.1')
Source18:      neutron-hyperv-agent.service
#end if
#if $older_than('2014.2')
Source19:      neutron-rpc-zmq-receiver.service
#end if
Source20:      neutron-metadata-agent.service
#if $newer_than('2014.2')
#if $older_than('2015.1')
Source21:      neutron-lbaas-agent.service
#end if
Source22:      neutron-mlnx-agent.service
#if $older_than('2015.1')
Source23:      neutron-vpn-agent.service
#end if
Source24:      neutron-metering-agent.service
Source25:      neutron-sriov-nic-agent.service
#if $older_than('2015.1')
Source26:      neutron-cisco-cfg-agent.service
#end if
Source27:      neutron-netns-cleanup.service
#end if
%endif

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

BuildArch:	noarch

BuildRequires:	python-devel
BuildRequires:	python-setuptools
BuildRequires:	python-pbr
# Build require these parallel versions
# as setup.py build imports neutron.openstack.common.setup
# which will then check for these
# BuildRequires:	python-sqlalchemy
# BuildRequires:	python-webob
# BuildRequires:	python-paste-deploy
# BuildRequires:	python-routes
BuildRequires:	dos2unix

Requires:	python-neutron = %{epoch}:%{version}-%{release}
Requires:       python-keystone

Provides:       openstack-neutron = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum < %{epoch}:%{version}-%{release}

%if ! 0%{?usr_only}
Requires(post):   chkconfig
Requires(postun): initscripts
Requires(preun):  chkconfig
Requires(preun):  initscripts
Requires(pre):    shadow-utils
%endif

%description
Neutron is a virtual network service for Openstack. Just like OpenStack
Nova provides an API to dynamically request and configure virtual
servers, Neutron provides an API to dynamically request and configure
virtual networks. These networks connect "interfaces" from other
OpenStack services (e.g., virtual NICs from Nova VMs). The Neutron API
supports extensions to provide advanced network capabilities (e.g., QoS,
ACLs, network monitoring, etc.)


%package -n python-neutron
Summary:	Neutron Python libraries
Group:		Applications/System

Provides:       python-neutron = %{epoch}:%{version}-%{release}
Obsoletes:      python-quantum < %{epoch}:%{version}-%{release}

Requires:	sudo
#for $i in $requires
Requires:	${i}
#end for

#for $i in $conflicts
Conflicts:       ${i}
#end for

%description -n python-neutron
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron Python library.

#if $newer_than_eq('2015.1')
%package -n openstack-neutron-common
Summary:        Neutron common files
Group:          Applications/System

Requires:       python-neutron = %{epoch}:%{version}-%{release}


%description -n openstack-neutron-common
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains Neutron common files.
#end if

%package -n openstack-neutron-bigswitch
Summary:	Neutron Big Switch plugin
Group:		Applications/System

Provides:       openstack-neutron-bigswitch = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-bigswitch < %{epoch}:%{version}-%{release}

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if

%description -n openstack-neutron-bigswitch
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using the FloodLight Openflow Controller or the Big Switch
Networks Controller.


%package -n openstack-neutron-brocade
Summary:	Neutron Brocade plugin
Group:		Applications/System

Provides:       openstack-neutron-brocade = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-brocade < %{epoch}:%{version}-%{release}


#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if


%description -n openstack-neutron-brocade
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using Brocade VCS switches running NOS.

%package -n openstack-neutron-cisco
Summary:	Neutron Cisco plugin
Group:		Applications/System

Provides:       openstack-neutron-cisco = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-cisco < %{epoch}:%{version}-%{release}

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if
Requires:	python-configobj


%description -n openstack-neutron-cisco
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using Cisco UCS and Nexus.

#if $newer_than_eq('2014.1')
%package -n openstack-neutron-embrane
Summary:	Neutron Embrane plugin
Group:		Applications/System

Provides:       openstack-neutron-embrane = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-embrane < %{epoch}:%{version}-%{release}

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if
Requires:	python-configobj


%description -n openstack-neutron-embrane
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using Embrane heleos platform.
#end if

#Upstream bascially rm -rf's this directory now... excuding going forward
#if $newer_than_eq('2015.1')
%package -n openstack-neutron-hyperv
Summary:	Neutron Hyper-V plugin
Group:		Applications/System

Provides:       openstack-neutron-hyperv = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-hyperv < %{epoch}:%{version}-%{release}

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if


%description -n openstack-neutron-hyperv
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using Microsoft Hyper-V.
#end if

#if $newer_than_eq('2014.1.b1')
%package -n openstack-neutron-ibm
Summary:        Neutron IBM plugin
Group:          Applications/System

Provides:       openstack-neutron-ibm = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-ibm < %{epoch}:%{version}-%{release}

Requires:       openstack-neutron = %{epoch}:%{version}-%{release}


%description -n openstack-neutron-ibm
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using IBM.
#end if

%package -n openstack-neutron-linuxbridge
Summary:	Neutron linuxbridge plugin
Group:		Applications/System

Provides:       openstack-neutron-linuxbridge = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-linuxbridge < %{epoch}:%{version}-%{release}

Requires:	bridge-utils
#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if
Requires:	python-pyudev


%description -n openstack-neutron-linuxbridge
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks as VLANs using Linux bridging.

#if $newer_than('2014.2')
%package -n openstack-neutron-metering-agent
Summary:        Neutron bandwidth metering agent
Group:          Applications/System

Requires:       openstack-neutron = %{epoch}:%{version}-%{release}

%description -n openstack-neutron-metering-agent
Neutron provides an API to measure bandwidth utilization

This package contains the Neutron agent responsible for generating bandwidth
utilization notifications.
#end if

%package -n openstack-neutron-midonet
Summary:	Neutron MidoNet plugin
Group:		Applications/System

Provides:       openstack-neutron-midonet = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-midonet < %{epoch}:%{version}-%{release}


#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if


%description -n openstack-neutron-midonet
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using MidoNet from Midokura.


%package -n openstack-neutron-ml2
Summary:	Neutron ML2 plugin
Group:		Applications/System

Provides:       openstack-neutron-ml2 = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-ml2 < %{epoch}:%{version}-%{release}

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if
Requires:       python-stevedore >= 0.9


%description -n openstack-neutron-ml2
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains a neutron plugin that allows the use of drivers to
support separately extensible sets of network types and the mechanisms
for accessing those types.

#if $older_than('2015.1')
%package -n openstack-neutron-mlnx
#end if
#if $newer_than_eq('2015.1')
%package -n openstack-neutron-mellanox
#end if
Summary:	Neutron Mellanox plugin
Group:		Applications/System

Provides:       openstack-neutron-mlnx = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-mlnx < %{epoch}:%{version}-%{release}

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if


#if $older_than('2015.1')
%description -n openstack-neutron-mlnx
#end if
#if $newer_than_eq('2015.1')
%description -n openstack-neutron-mellanox
#end if

Neutron provides an API to dynamically request and configure virtual
networks.

This plugin implements Quantum v2 APIs with support for Mellanox
embedded switch functionality as part of the VPI (Ethernet/InfiniBand)
HCA.

#if $older_than('2014.1')
%package -n openstack-neutron-nicira
Summary:	Neutron Nicira plugin
Group:		Applications/System

Provides:       openstack-neutron-nicira = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-nicira < %{epoch}:%{version}-%{release}

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if


%description -n openstack-neutron-nicira
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using Nicira NVP.
#end if


#if $newer_than_eq('2014.1')
%package -n openstack-neutron-nuage
Summary:	Neutron Nuage plugin
Group:		Applications/System

Provides:       openstack-neutron-nuage = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-nuage < %{epoch}:%{version}-%{release}

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if
Requires:	python-configobj


%description -n openstack-neutron-nuage
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using Nuage Networks’ Virtual Service Platform (VSP).
#end if


#if $newer_than_eq('2014.1')
%package -n openstack-neutron-ofagent
Summary:        Neutron ofagent plugin
Group:          Applications/System

Provides:       openstack-neutron-ofagent = %{epoch}:%{version}-%{release}

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if


%description -n openstack-neutron-ofagent
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using ofagent.
#end if

#if $newer_than('2014.2')
%package -n openstack-neutron-opencontrail
Summary:        Neutron OpenContrail plugin
Group:          Applications/system

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if


%description -n openstack-neutron-opencontrail
This plugin implements Neutron v2 APIs with support for the OpenContrail
plugin.
#end if

%package -n openstack-neutron-openvswitch
Summary:	Neutron openvswitch plugin
Group:		Applications/System

Provides:       openstack-neutron-openvswitch = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-openvswitch < %{epoch}:%{version}-%{release}

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if
Requires:	openvswitch


%description -n openstack-neutron-openvswitch
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using Open vSwitch.

#if $newer_than_eq('2014.1.b1')
%package -n openstack-neutron-oneconvergence-nvsd
Summary:        Neutron oneconvergence plugin
Group:          Applications/System

Provides:       openstack-neutron-oneconvergence-nvsd = %{epoch}:%{version}-%{release}

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if


%description -n openstack-neutron-oneconvergence-nvsd
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using oneconvergence nvsd.
#end if

#if $newer_than_eq('2015.1')
%package -n openstack-neutron-ovsvapp
Summary:	Neutron OVSvApp vSphere plugin
Group:		Applications/System

Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}


%description ovsvapp
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the Neutron plugin that implements virtual
networks using OVSvApp vSphere L2 agent.
#end if

%package -n openstack-neutron-plumgrid
Summary:	Neutron PLUMgrid plugin
Group:		Applications/System

Provides:       openstack-neutron-plumgrid = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-plumgrid < %{epoch}:%{version}-%{release}

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if


%description -n openstack-neutron-plumgrid
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using the PLUMgrid platform.

#if $older_than('2015.1')
%package -n openstack-neutron-ryu
Summary:	Neutron Ryu plugin
Group:		Applications/System

Provides:       openstack-neutron-ryu = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-ryu < %{epoch}:%{version}-%{release}

Requires:	openstack-neutron = %{epoch}:%{version}-%{release}

%description -n openstack-neutron-ryu
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using the Ryu Network Operating System.
#end if

#if $newer_than('2014.2')
%package -n openstack-neutron-sriov-nic-agent
Summary:        Neutron SR-IOV NIC agent
Group:          Applications/system

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if


%description -n openstack-neutron-sriov-nic-agent
Neutron allows to run virtual instances using SR-IOV NIC hardware

This package contains the Neutron agent to support advanced features of
SR-IOV network cards.
#end if

%package -n openstack-neutron-nec
Summary:	Neutron NEC plugin
Group:		Applications/System

Provides:       openstack-neutron-nec = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-nec < %{epoch}:%{version}-%{release}

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if


%description -n openstack-neutron-nec
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using the NEC OpenFlow controller.


%package -n openstack-neutron-metaplugin
Summary:	Neutron meta plugin
Group:		Applications/System

Provides:       openstack-neutron-metaplugin = %{epoch}:%{version}-%{release}
Obsoletes:      openstack-quantum-metaplugin < %{epoch}:%{version}-%{release}

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if

%description -n openstack-neutron-metaplugin
Neutron provides an API to dynamically request and configure virtual
networks.

This package contains the neutron plugin that implements virtual
networks using multiple other neutron plugins.

#if $newer_than_eq('2014.1.b1')
%package -n openstack-neutron-vmware
Summary:       Neutron VMWare NSX support
Group:         Applications/System

#if $older_than('2015.1')
Requires:	openstack-neutron = %{epoch}:%{version}-%{release}
#end if
#if $newer_than_eq('2015.1')
Requires:	openstack-neutron-common = %{epoch}:%{version}-%{release}
#end if
Provides:      openstack-neutron-nicira = %{epoch}:%{version}-%{release}
Obsoletes:     openstack-neutron-nicera < %{epoch}:%{version}-%{release}

%description -n openstack-neutron-vmware
Neutron provides an API to dynamically request and configure virtual
networks.

This package adds VMWare NSX support for Neutron,
#end if

#if $newer_than('2014.2')
#if $older_than('2015.1')
%package -n openstack-neutron-vpn-agent
Summary:        Neutron VPNaaS agent
Group:          Applications/System

Requires:	openstack-neutron = %{epoch}:%{version}-%{release}

%description -n openstack-neutron-vpn-agent
Neutron provides an API to implement VPN as a service

This package contains the Neutron agent responsible for implementing VPNaaS with
IPSec.
#end if
#end if

%if ! 0%{?no_tests}
%package -n python-%{python_name}-tests
Summary:          Tests for Quantum
Group:            Development/Libraries

Requires:         %{name} = %{epoch}:%{version}-%{release}
Requires:         %{name}-bigswitch = %{epoch}:%{version}-%{release}
Requires:         %{name}-brocade = %{epoch}:%{version}-%{release}
Requires:         %{name}-cisco = %{epoch}:%{version}-%{release}
#if $older_than('2015.1')
Requires:         %{name}-hyperv = %{epoch}:%{version}-%{release}
#end if
Requires:         %{name}-linuxbridge = %{epoch}:%{version}-%{release}
Requires:         %{name}-midonet = %{epoch}:%{version}-%{release}
Requires:         %{name}-nicira = %{epoch}:%{version}-%{release}
Requires:         %{name}-openvswitch = %{epoch}:%{version}-%{release}
Requires:         %{name}-plumgrid = %{epoch}:%{version}-%{release}
#if $older_than('2015.1')
Requires:         %{name}-ryu = %{epoch}:%{version}-%{release}
#end if
#if $newer_than('2015.1')
Requires:         %{name}-ofagent = %{epoch}:%{version}-%{release}
#end if
Requires:         %{name}-nec = %{epoch}:%{version}-%{release}
Requires:         %{name}-metaplugin = %{epoch}:%{version}-%{release}
#if $older_than('2015.1')
Requires:         %{name}-mlnx = %{epoch}:%{version}-%{release}
#end if
Requires:         %{name}-nuage = %{epoch}:%{version}-%{release}
Requires:         python-neutron = %{epoch}:%{version}-%{release}
#if $newer_than_eq('2015.1')
Requires:         python-neutron-common = %{epoch}:%{version}-%{release}
#end if
# Test requirements:
#for $i in $test_requires
Requires:         ${i}
#end for

%description -n python-%{python_name}-tests
Quantum provides an API to dynamically request and configure virtual
networks.

This package contains unit and functional tests for Quantum, with
simple runner (%{python_name}-make-test-env).
%endif

%prep
%setup -q -n neutron-%{os_version}
#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for
#raw

find neutron -name \*.py -exec sed -i '/\/usr\/bin\/env python/d' {} \;

chmod 644 neutron/plugins/cisco/README

# Adjust configuration file content
sed -i 's/debug = True/debug = False/' etc/neutron.conf
sed -i 's/\# auth_strategy = keystone/auth_strategy = keystone/' etc/neutron.conf

# Remove unneeded dependency
sed -i '/setuptools_git/d' setup.py

# let RPM handle deps
sed -i '/setup_requires/d; /install_requires/d; /dependency_links/d' setup.py


%build

export PBR_VERSION=$version
%{__python} setup.py build


%install

export PBR_VERSION=$version
rm -rf %{buildroot}
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

%if ! 0%{?no_tests}
#end raw
#include $part_fn("install_tests.sh")
#raw
%endif

# Remove unused files
rm -rf %{buildroot}%{python_sitelib}/bin
rm -rf %{buildroot}%{python_sitelib}/doc
rm -rf %{buildroot}%{python_sitelib}/tools
rm -f %{buildroot}%{python_sitelib}/neutron/plugins/*/run_tests.*
rm %{buildroot}/usr/etc/init.d/neutron-server

# Install execs
install -p -D -m 755 bin/* %{buildroot}%{_bindir}/

# Move rootwrap files to proper location
install -d -m 755 %{buildroot}%{_datarootdir}/neutron/rootwrap
mv %{buildroot}/usr/etc/neutron/rootwrap.d/*.filters %{buildroot}%{_datarootdir}/neutron/rootwrap

%if ! 0%{?usr_only}
# Move config files to proper location
install -d -m 755 %{buildroot}%{_sysconfdir}/neutron
mv %{buildroot}/usr/etc/neutron/* %{buildroot}%{_sysconfdir}/neutron
chmod 640  %{buildroot}%{_sysconfdir}/neutron/plugins/*/*.ini

# Configure agents to use neutron-rootwrap
for f in %{buildroot}%{_sysconfdir}/neutron/plugins/*/*.ini %{buildroot}%{_sysconfdir}/neutron/*_agent.ini; do
    sed -i 's/^root_helper.*/root_helper = sudo neutron-rootwrap \/etc\/neutron\/rootwrap.conf/g' $f
done

# Configure neutron-dhcp-agent state_path
sed -i 's/state_path = \/opt\/stack\/data/state_path = \/var\/lib\/neutron/' %{buildroot}%{_sysconfdir}/neutron/dhcp_agent.ini

# Install logrotate
install -p -D -m 644 %{SOURCE1} %{buildroot}%{_sysconfdir}/logrotate.d/openstack-neutron

# Install sudoers
install -p -D -m 440 %{SOURCE2} %{buildroot}%{_sysconfdir}/sudoers.d/neutron

#end raw
# Install sysv init scripts
%if ! (0%{?rhel} > 6)
install -p -D -m 755 %{SOURCE10} %{buildroot}%{_initrddir}/%{daemon_prefix}-server
install -p -D -m 755 %{SOURCE11} %{buildroot}%{_initrddir}/%{daemon_prefix}-linuxbridge-agent
install -p -D -m 755 %{SOURCE12} %{buildroot}%{_initrddir}/%{daemon_prefix}-openvswitch-agent
#if $older_than('2015.1')
install -p -D -m 755 %{SOURCE13} %{buildroot}%{_initrddir}/%{daemon_prefix}-ryu-agent
#end if
install -p -D -m 755 %{SOURCE14} %{buildroot}%{_initrddir}/%{daemon_prefix}-nec-agent
install -p -D -m 755 %{SOURCE15} %{buildroot}%{_initrddir}/%{daemon_prefix}-dhcp-agent
install -p -D -m 755 %{SOURCE16} %{buildroot}%{_initrddir}/%{daemon_prefix}-l3-agent
install -p -D -m 755 %{SOURCE17} %{buildroot}%{_initrddir}/%{daemon_prefix}-ovs-cleanup
#if $older_than('2015.1')
install -p -D -m 755 %{SOURCE18} %{buildroot}%{_initrddir}/%{daemon_prefix}-hyperv-agent
#end if
#if $older_than('2014.2')
install -p -D -m 755 %{SOURCE19} %{buildroot}%{_initrddir}/%{daemon_prefix}-rpc-zmq-receiver
#end if
install -p -D -m 755 %{SOURCE20} %{buildroot}%{_initrddir}/%{daemon_prefix}-metadata-agent
#if $newer_than('2014.2')
#if $older_than('2015.1')
install -p -D -m 755 %{SOURCE21} %{buildroot}%{_initrddir}/%{daemon_prefix}-lbaas-agent
install -p -D -m 755 %{SOURCE23} %{buildroot}%{_initrddir}/%{daemon_prefix}-vpn-agent
#end if
install -p -D -m 755 %{SOURCE22} %{buildroot}%{_initrddir}/%{daemon_prefix}-mlnx-agent
install -p -D -m 755 %{SOURCE24} %{buildroot}%{_initrddir}/%{daemon_prefix}-metering-agent
install -p -D -m 755 %{SOURCE25} %{buildroot}%{_initrddir}/%{daemon_prefix}-sriov-nic-agent
#if $older_than('2015.1')
install -p -D -m 755 %{SOURCE26} %{buildroot}%{_initrddir}/%{daemon_prefix}-cisco-cfg-agent
#end if
install -p -D -m 755 %{SOURCE27} %{buildroot}%{_initrddir}/%{daemon_prefix}-netns-cleanup
#end if
%else
install -p -D -m 755 %{SOURCE10} %{buildroot}%{_unitdir}/%{daemon_prefix}-server.service
install -p -D -m 755 %{SOURCE11} %{buildroot}%{_unitdir}/%{daemon_prefix}-linuxbridge-agent.service
install -p -D -m 755 %{SOURCE12} %{buildroot}%{_unitdir}/%{daemon_prefix}-openvswitch-agent.service
#if $older_than('2015.1')
install -p -D -m 755 %{SOURCE13} %{buildroot}%{_unitdir}/%{daemon_prefix}-ryu-agent.service
#end if
install -p -D -m 755 %{SOURCE14} %{buildroot}%{_unitdir}/%{daemon_prefix}-nec-agent.service
install -p -D -m 755 %{SOURCE15} %{buildroot}%{_unitdir}/%{daemon_prefix}-dhcp-agent.service
install -p -D -m 755 %{SOURCE16} %{buildroot}%{_unitdir}/%{daemon_prefix}-l3-agent.service
install -p -D -m 755 %{SOURCE17} %{buildroot}%{_unitdir}/%{daemon_prefix}-ovs-cleanup.service
#if $older_than('2015.1')
install -p -D -m 755 %{SOURCE18} %{buildroot}%{_unitdir}/%{daemon_prefix}-hyperv-agent.service
#end if
#if $older_than('2014.2')
install -p -D -m 755 %{SOURCE19} %{buildroot}%{_unitdir}/%{daemon_prefix}-rpc-zmq-receiver.service
#end if
install -p -D -m 755 %{SOURCE20} %{buildroot}%{_unitdir}/%{daemon_prefix}-metadata-agent.service
#if $newer_than('2014.2')
#if $older_than('2015.1')
install -p -D -m 755 %{SOURCE21} %{buildroot}%{_unitdir}/%{daemon_prefix}-lbaas-agent.service
install -p -D -m 755 %{SOURCE23} %{buildroot}%{_unitdir}/%{daemon_prefix}-vpn-agent.service
#end if
install -p -D -m 755 %{SOURCE22} %{buildroot}%{_unitdir}/%{daemon_prefix}-mlnx-agent.service
install -p -D -m 755 %{SOURCE24} %{buildroot}%{_unitdir}/%{daemon_prefix}-metering-agent.service
install -p -D -m 755 %{SOURCE25} %{buildroot}%{_unitdir}/%{daemon_prefix}-sriov-nic-agent.service
#if $older_than('2015.1')
install -p -D -m 755 %{SOURCE26} %{buildroot}%{_unitdir}/%{daemon_prefix}-cisco-cfg-agent.service
#end if
install -p -D -m 755 %{SOURCE27} %{buildroot}%{_unitdir}/%{daemon_prefix}-netns-cleanup.service
#end if
%endif

# Setup directories
install -d -m 755 %{buildroot}%{_sharedstatedir}/neutron
install -d -m 755 %{buildroot}%{_localstatedir}/log/neutron
install -d -m 755 %{buildroot}%{_localstatedir}/lock/neutron
install -d -m 755 %{buildroot}%{_localstatedir}/run/neutron

#remove hyperv from linux to match upstream
#if $newer_than_eq('2015.1')
rm %{buildroot}/%{_bindir}/neutron-hyperv-agent
#end if

#if $newer_than_eq('2015.1')
# Create configuration directories for all services that can be populated by users with custom *.conf files
mkdir -p %{buildroot}/%{_sysconfdir}/neutron/conf.d/common

#raw
# Create and populate configuration directory for L3 agent that is not accessible for user modification
mkdir -p %{buildroot}%{_datadir}/neutron/l3_agent
ln -s %{_sysconfdir}/neutron/l3_agent.ini %{buildroot}%{_datadir}/neutron/l3_agent/l3_agent.conf

# Create dist configuration directory for neutron-server (may be filled by advanced services)
mkdir -p %{buildroot}%{_datadir}/neutron/server

# Create configuration directories for all services that can be populated by users with custom *.conf files
mkdir -p %{buildroot}/%{_sysconfdir}/neutron/conf.d/common
for service in server ovs-cleanup netns-cleanup; do
    mkdir -p %{buildroot}/%{_sysconfdir}/neutron/conf.d/neutron-$service
done
for service in linuxbridge openvswitch nec dhcp l3 metadata mlnx metering sriov-nic; do
    mkdir -p %{buildroot}/%{_sysconfdir}/neutron/conf.d/neutron-$service-agent
done
#end raw
#end if

#raw
# Install version info file
cat > %{buildroot}%{_sysconfdir}/neutron/release <<EOF
[Neutron]
vendor = OpenStack LLC
product = OpenStack Neutron
package = %{release}
EOF
%else
rm -rf %{buildroot}/usr/etc/
%endif

%clean
rm -rf %{buildroot}


%if ! 0%{?usr_only}
%pre
getent group neutron >/dev/null || groupadd -r neutron
getent passwd neutron >/dev/null || \
useradd -r -g neutron -d %{_sharedstatedir}/neutron -s /sbin/nologin \
-c "OpenStack Neutron Daemons" neutron
exit 0

# Do not autostart daemons in %post since they are not configured yet
#end raw
#if $older_than('2014.2')
#set $daemon_map = {"": ["server", "dhcp-agent", "l3-agent"], "linuxbridge": ["linuxbridge-agent"], "openvswitch": ["openvswitch-agent", "ovs-cleanup"], "ryu": ["ryu-agent"], "nec": ["nec-agent"]}
#end if
#if $newer_than_eq('2014.2')
#set $daemon_map = {"": ["server", "dhcp-agent", "l3-agent", "lbaas-agent", "netns-cleanup"], "linuxbridge": ["linuxbridge-agent"], "openvswitch": ["openvswitch-agent", "ovs-cleanup"], "ryu": ["ryu-agent"], "nec": ["nec-agent"], "mlnx": ["mlnx-agent"], "vpn-agent": ["vpn-agent"], "metering-agent": ["metering-agent"], "sriov-nic-agent": ["sriov-nic-agent"], "cisco": ["cisco-cfg-agent"]}
#end if
#if $newer_than_eq('2015.1')
#set $daemon_map = {"": ["server", "dhcp-agent", "l3-agent", "netns-cleanup"], "linuxbridge": ["linuxbridge-agent"], "openvswitch": ["openvswitch-agent", "ovs-cleanup"], "nec": ["nec-agent"], "metering-agent": ["metering-agent"], "sriov-nic-agent": ["sriov-nic-agent"]}
#end if
#for $key, $value in $daemon_map.iteritems()
#set $daemon_list = " ".join($value) if $value else $key

%if 0%{?rhel} > 6
%post $key
if [ \$1 -eq 1 ] ; then
    # Initial installation
    for svc in $daemon_list; do
        /usr/bin/systemctl preset %{daemon_prefix}-\${svc}.service
    done
fi
%endif

%preun $key
if [ \$1 -eq 0 ] ; then
    for svc in $daemon_list; do
%if ! (0%{?rhel} > 6)
        /sbin/service %{daemon_prefix}-\${svc} stop &>/dev/null
        /sbin/chkconfig --del %{daemon_prefix}-\${svc}
%else
        /usr/bin/systemctl --no-reload disable %{daemon_prefix}-\${svc}.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{daemon_prefix}-\${svc}.service > /dev/null 2>&1 || :
%endif
    done
    exit 0
fi

#end for
%endif

%files
%doc README* LICENSE HACKING* ChangeLog AUTHORS
%{_bindir}/*-db-manage
%{_bindir}/*-debug
%{_bindir}/*-dhcp-agent
%{_bindir}/*-l3-agent
#if $older_than('2015.1')
%{_bindir}/*-lbaas-agent
#end if
%{_bindir}/*-metadata-agent
#if $older_than('2014.2')
%{_bindir}/*-metering-agent
#end if
%{_bindir}/*-netns-cleanup
%{_bindir}/*-ns-metadata-proxy
#if $older_than('2015.1')
%{_bindir}/*-rootwrap
#end if
#if $older_than('2014.2')
%{_bindir}/*-rpc-zmq-receiver
#end if
%{_bindir}/*-server
%{_bindir}/*-usage-audit
#if $older_than('2014.2')
%{_bindir}/*-vpn-agent
#end if
#if $newer_than('2014.2')
%{_bindir}/neutron-sanity-check
#end if
#if $newer_than_eq('2015.1')
%{_bindir}/neutron-keepalived-state-change
#end if

#if $older_than('2015.1')
%{_datarootdir}/neutron
#end if
%exclude %{_datarootdir}/neutron/rootwrap/linuxbridge-plugin.filters
%exclude %{_datarootdir}/neutron/rootwrap/openvswitch-plugin.filters
#if $older_than('2015.1')
%exclude %{_datarootdir}/neutron/rootwrap/ryu-plugin.filters
#end if
%exclude %{_datarootdir}/neutron/rootwrap/nec-plugin.filters

%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-server
%{_initrddir}/%{daemon_prefix}-dhcp-agent
%{_initrddir}/%{daemon_prefix}-l3-agent
%{_initrddir}/%{daemon_prefix}-metadata-agent
#if $older_than('2014.2')
%{_initrddir}/%{daemon_prefix}-rpc-zmq-receiver
#end if
#if $newer_than('2014.2')
%{_initrddir}/%{daemon_prefix}-lbaas-agent
%{_initrddir}/%{daemon_prefix}-netns-cleanup
#end if
%else
%{_unitdir}/%{daemon_prefix}-server.service
%{_unitdir}/%{daemon_prefix}-dhcp-agent.service
%{_unitdir}/%{daemon_prefix}-l3-agent.service
%{_unitdir}/%{daemon_prefix}-metadata-agent.service
#if $older_than('2014.2')
%{_unitdir}/%{daemon_prefix}-rpc-zmq-receiver.service
#end if
#if $newer_than('2014.2')
#if $older_than('2015.1')
%{_unitdir}/%{daemon_prefix}-lbaas-agent.service
#end if
%{_unitdir}/%{daemon_prefix}-netns-cleanup.service
#end if
%endif
%dir %{_sysconfdir}/neutron
%{_sysconfdir}/neutron/release
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/policy.json
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/neutron.conf
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/*.ini
#if $older_than('2015.1')
%configfile %{_sysconfdir}/neutron/rootwrap.conf
%dir %{_sysconfdir}/neutron/plugins
%configfile %{_sysconfdir}/logrotate.d/*
%configfile %{_sysconfdir}/sudoers.d/neutron
%dir %attr(0755, neutron, neutron) %{_sharedstatedir}/neutron
%dir %attr(0755, neutron, neutron) %{_localstatedir}/log/neutron
%dir %attr(0755, neutron, neutron) %{_localstatedir}/lock/neutron
%dir %attr(0755, neutron, neutron) %{_localstatedir}/run/neutron
#end if
#if $newer_than_eq('2015.1')
%dir %{_datadir}/neutron/l3_agent
%dir %{_datadir}/neutron/server
%{_datadir}/neutron/l3_agent/*.conf
%dir %{_sysconfdir}/neutron/conf.d/neutron-dhcp-agent
%dir %{_sysconfdir}/neutron/conf.d/neutron-l3-agent
%dir %{_sysconfdir}/neutron/conf.d/neutron-metadata-agent
%dir %{_sysconfdir}/neutron/conf.d/neutron-server
%dir %{_sysconfdir}/neutron/conf.d/neutron-netns-cleanup
%dir %{_sysconfdir}/neutron/conf.d/neutron-ovs-cleanup
#end if
%endif

%files -n python-neutron
%doc LICENSE
#if $older_than('2015.1')
#if $older_than('2014.2')
%{python_sitelib}/neutron
%{python_sitelib}/quantum
#end if
%exclude %{python_sitelib}/neutron/tests
%exclude %{python_sitelib}/neutron/plugins/bigswitch
%exclude %{python_sitelib}/neutron/plugins/brocade
%exclude %{python_sitelib}/neutron/plugins/cisco
%exclude %{python_sitelib}/neutron/plugins/hyperv
%exclude %{python_sitelib}/neutron/plugins/linuxbridge
%exclude %{python_sitelib}/neutron/plugins/metaplugin
%exclude %{python_sitelib}/neutron/plugins/midonet
%exclude %{python_sitelib}/neutron/plugins/nec
%exclude %{python_sitelib}/neutron/plugins/ml2
%exclude %{python_sitelib}/neutron/plugins/mlnx
#if $older_than('2014.2')
%exclude %{python_sitelib}/neutron/plugins/nicira
#end if
%exclude %{python_sitelib}/neutron/plugins/openvswitch
%exclude %{python_sitelib}/neutron/plugins/plumgrid
%exclude %{python_sitelib}/neutron/plugins/ryu
#if $newer_than_eq('2014.1')
%exclude %{python_sitelib}/neutron/plugins/embrane
%exclude %{python_sitelib}/neutron/plugins/nuage
#end if
#if $newer_than_eq('2014.1.b1')
%exclude %{python_sitelib}/neutron/plugins/ibm
%exclude %{python_sitelib}/neutron/plugins/ofagent
%exclude %{python_sitelib}/neutron/plugins/oneconvergence
%exclude %{python_sitelib}/neutron/plugins/vmware
#end if
#if $newer_than_eq('2014.2')
%exclude %{python_sitelib}/neutron/plugins/opencontrail
#end if
#end if
#if $newer_than_eq('2015.1')
%{python_sitelib}/neutron
%exclude %{python_sitelib}/neutron/tests
#end if
%{python_sitelib}/neutron-*.egg-info

#if $newer_than_eq('2015.1')
%files -n python-neutron-tests
%license LICENSE
%{python2_sitelib}/neutron/tests
#endif

#if $newer_than_eq('2015.1')
%files -n openstack-neutron-common
%license LICENSE
%doc README.rst
%{_bindir}/neutron-rootwrap
%{_bindir}/neutron-rootwrap-daemon
%{_bindir}/neutron-rootwrap-xen-dom0
%dir %{_sysconfdir}/neutron
%dir %{_sysconfdir}/neutron/conf.d
%dir %{_sysconfdir}/neutron/conf.d/common
%dir %{_sysconfdir}/neutron/plugins
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/neutron.conf
%configfile %{_sysconfdir}/neutron/rootwrap.conf
%configfile %{_sysconfdir}/logrotate.d/*
%{_sysconfdir}/sudoers.d/neutron
%dir %attr(0755, neutron, neutron) %{_sharedstatedir}/neutron
%dir %attr(0750, neutron, neutron) %{_localstatedir}/log/neutron
%dir %{_datarootdir}/neutron
%dir %{_datarootdir}/neutron/rootwrap
%{_datarootdir}/neutron/rootwrap/debug.filters
%{_datarootdir}/neutron/rootwrap/dhcp.filters
%{_datarootdir}/neutron/rootwrap/ipset-firewall.filters
%{_datarootdir}/neutron/rootwrap/iptables-firewall.filters
%{_datarootdir}/neutron/rootwrap/l3.filters
#end if

%files -n openstack-neutron-bigswitch
%doc LICENSE
#if $older_than('2015.1')
%doc neutron/plugins/bigswitch/README
#end if
#if $newer_than_eq('2014.1.b1')
%{_bindir}/neutron-restproxy-agent
#end if
%{python_sitelib}/neutron/plugins/bigswitch
#if $older_than('2015.1')
%exclude %{python_sitelib}/neutron/plugins/bigswitch/tests
#end if

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/bigswitch
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/bigswitch/*.ini
#if $newer_than_eq('2014.1.dev146.g79fbeb7')
%doc %{_sysconfdir}/neutron/plugins/bigswitch/ssl/*
#end if
%endif

%files -n openstack-neutron-brocade
%doc LICENSE
%doc neutron/plugins/brocade/README.md
%{python_sitelib}/neutron/plugins/brocade
%exclude %{python_sitelib}/neutron/plugins/brocade/tests

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/brocade
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/brocade/*.ini
#if $newer_than_eq('2015.1')
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/brocade/vyatta/*.ini
#end if
%endif


%files -n openstack-neutron-cisco
%doc LICENSE
%doc neutron/plugins/cisco/README
%{python_sitelib}/neutron/plugins/cisco
#if $older_than('2015.1')
#if $newer_than('2014.2')
%{_bindir}/neutron-cisco-cfg-agent
#end if
#end if
#if $newer_than_eq('2015.1')
%{_bindir}/neutron-cisco-apic-host-agent
%{_bindir}/neutron-cisco-apic-service-agent
#end if

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/cisco
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/cisco/*.ini
#if $older_than('2015.1')
#if $newer_than('2014.2')
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-cisco-cfg-agent
%else
%{_unitdir}/%{daemon_prefix}-cisco-cfg-agent.service
%endif
#end if
#end if
%endif

#if $newer_than_eq('2014.1.1')
%files -n openstack-neutron-embrane
%doc LICENSE
%doc neutron/plugins/embrane/README
%{python_sitelib}/neutron/plugins/embrane

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/embrane
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/embrane/*.ini
%endif
#end if

#if $older_than('2015.1')
%files -n openstack-neutron-hyperv
%doc LICENSE
%{_bindir}/*-hyperv-agent
%{python_sitelib}/neutron/plugins/hyperv
%exclude %{python_sitelib}/neutron/plugins/hyperv/agent

%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-hyperv-agent
%else
%{_unitdir}/%{daemon_prefix}-hyperv-agent.service
%endif
%dir %{_sysconfdir}/neutron/plugins/hyperv
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/hyperv/*.ini
%endif
#end if

#if $newer_than_eq('2014.1.b1')
%files -n openstack-neutron-ibm
%doc LICENSE
%doc neutron/plugins/ibm/README
%{_bindir}/*-ibm-agent
%{python_sitelib}/neutron/plugins/ibm

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/ibm
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/ibm/*.ini
%endif
#end if

%files -n openstack-neutron-linuxbridge
%doc LICENSE
%doc neutron/plugins/linuxbridge/README
%{_bindir}/*-linuxbridge-agent
%{python_sitelib}/neutron/plugins/linuxbridge
%{_datarootdir}/neutron/rootwrap/linuxbridge-plugin.filters

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/linuxbridge
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-linuxbridge-agent
%else
%{_unitdir}/%{daemon_prefix}-linuxbridge-agent.service
%endif
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/linuxbridge/*.ini
%endif

#if $newer_than('2014.2')
%files -n openstack-neutron-metering-agent
%doc LICENSE
%{_bindir}/neutron-metering-agent

%if ! 0%{?usr_only}
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/metering_agent.ini
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-metering-agent
%else
%{_unitdir}/%{daemon_prefix}-metering-agent.service
%endif
%endif
#end if

%files -n openstack-neutron-midonet
%doc LICENSE
%{python_sitelib}/neutron/plugins/midonet

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/midonet
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/midonet/*.ini
%endif

%files -n openstack-neutron-ml2
%doc LICENSE
%doc neutron/plugins/ml2/README
%{python_sitelib}/neutron/plugins/ml2

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/ml2
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/ml2/*.ini
%endif

#if $older_than('2015.1')
%files -n openstack-neutron-mlnx
#end if
#if $newer_than_eq('2015.1')
%files -n openstack-neutron-mellanox
#end if
%doc LICENSE
#if $older_than('2015.1')
%doc neutron/plugins/mlnx/README
#end if
#if $newer_than_eq('2015.1')
%doc neutron/plugins/ml2/drivers/mlnx/README
#end if
%{_bindir}/*-mlnx-agent
#if $older_than('2015.1')
%{python_sitelib}/neutron/plugins/mlnx
#end if

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/mlnx
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/mlnx/*.ini
#if $newer_than('2014.2')
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-mlnx-agent
%else
%{_unitdir}/%{daemon_prefix}-mlnx-agent.service
%endif
#end if
%endif
#end if

#if $older_than('2014.1')
%files -n openstack-neutron-nicira
%doc LICENSE
%doc neutron/plugins/nicira/README
%{_bindir}/*-check-nvp-config
%{python_sitelib}/neutron/plugins/nicira

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/nicira
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/nicira/*.ini
%endif
#end if

#if $newer_than_eq('2014.1')
%files -n openstack-neutron-nuage
%doc LICENSE
%{python_sitelib}/neutron/plugins/nuage
#end if

#if $newer_than_eq('2014.1.1')
%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/nuage
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/nuage/*.ini
%endif
#end if

#if $newer_than_eq('2014.1.b1')
%files -n openstack-neutron-ofagent
%doc LICENSE
#if $older_than('2015.1')
%{_bindir}/*-ofagent-agent
%doc neutron/plugins/ofagent/README
%{python_sitelib}/neutron/plugins/ofagent
#end if
#end if

#if $newer_than('2014.2')
%files -n openstack-neutron-opencontrail
%doc LICENSE
%{python_sitelib}/neutron/plugins/opencontrail

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/opencontrail
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/opencontrail/*.ini
%endif
#end if

#if $newer_than_eq('2014.1.b1')
%files -n openstack-neutron-oneconvergence-nvsd
%doc LICENSE
%doc neutron/plugins/oneconvergence/README
%{_bindir}/*-nvsd-agent
%{python_sitelib}/neutron/plugins/oneconvergence

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/oneconvergence
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/oneconvergence/*.ini
%endif
#end if

%files -n openstack-neutron-openvswitch
%doc LICENSE
%doc neutron/plugins/openvswitch/README
%{_bindir}/*-openvswitch-agent
%{_bindir}/*-ovs-cleanup
#if $older_than('2015.1')
%{_bindir}/*-rootwrap-xen-dom0
#end if
%{_datarootdir}/neutron/rootwrap/openvswitch-plugin.filters
%{python_sitelib}/neutron/plugins/openvswitch

%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-openvswitch-agent
%{_initrddir}/%{daemon_prefix}-ovs-cleanup
%else
%{_unitdir}/%{daemon_prefix}-openvswitch-agent.service
%{_unitdir}/%{daemon_prefix}-ovs-cleanup.service
%endif
%dir %{_sysconfdir}/neutron/plugins/openvswitch
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/openvswitch/*.ini
%endif

#if $newer_than_eq('2015.1')
%files -n openstack-neutron-ovsvapp
%license LICENSE
%{_bindir}/neutron-ovsvapp-agent

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/ovsvapp
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/ovsvapp/*.ini
%endif
#end if

%files -n openstack-neutron-plumgrid
%doc LICENSE
%doc neutron/plugins/plumgrid/README
%{python_sitelib}/neutron/plugins/plumgrid

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/plumgrid
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/plumgrid/*.ini
%endif

#if $older_than('2015.1')
%files -n openstack-neutron-ryu
%doc LICENSE
%doc neutron/plugins/ryu/README
%{_bindir}/*-ryu-agent
%{python_sitelib}/neutron/plugins/ryu
%{_datarootdir}/neutron/rootwrap/ryu-plugin.filters

%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-ryu-agent
%else
%{_unitdir}/%{daemon_prefix}-ryu-agent.service
%endif
%dir %{_sysconfdir}/neutron/plugins/ryu
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/ryu/*.ini
%endif
#end if

#if $newer_than('2014.2')
%files -n openstack-neutron-sriov-nic-agent
%doc LICENSE
%{_bindir}/neutron-sriov-nic-agent

%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-sriov-nic-agent
%else
%{_unitdir}/%{daemon_prefix}-sriov-nic-agent.service
%endif
%endif
#end if

%files -n openstack-neutron-nec
%doc LICENSE
%doc neutron/plugins/nec/README
%{_bindir}/*-nec-agent
%{python_sitelib}/neutron/plugins/nec
%{_datarootdir}/neutron/rootwrap/nec-plugin.filters

%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-nec-agent
%else
%{_unitdir}/%{daemon_prefix}-nec-agent.service
%endif
%dir %{_sysconfdir}/neutron/plugins/nec
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/nec/*.ini
%endif

#if $newer_than_eq('2014.1.b1')
%files -n openstack-neutron-vmware
%doc LICENSE
#if $older_than('2015.1')
%{_bindir}/neutron*nsx-*
#end if
#if $older_than('2014.2')
%{_bindir}/*-check-nvp-config
#end if
%{python_sitelib}/neutron/plugins/vmware

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/vmware
#if $older_than('2014.2')
%dir %{_sysconfdir}/neutron/plugins/nicira
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/nicira/*.ini
#end if
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/vmware/*.ini
%endif
#end if

%files -n openstack-neutron-metaplugin
%doc LICENSE
%doc neutron/plugins/metaplugin/README
%{python_sitelib}/neutron/plugins/metaplugin

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/neutron/plugins/metaplugin
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/plugins/metaplugin/*.ini
%endif

%if ! 0%{?no_tests}
%files -n python-%{python_name}-tests
%{tests_data_dir}
%{_bindir}/%{python_name}-make-test-env
%endif

#if $newer_than('2014.2')
#if $older_than('2015.1')
%files -n openstack-neutron-vpn-agent
%doc LICENSE
%{_bindir}/neutron-vpn-agent
%{_datarootdir}/neutron/rootwrap/vpnaas.filters
%if ! 0%{?usr_only}
%configfile %attr(0640, root, neutron) %{_sysconfdir}/neutron/vpn_agent.ini
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-vpn-agent
%else
%{_unitdir}/%{daemon_prefix}-vpn-agent.service
%endif
%endif
#end if
#end if
%changelog
