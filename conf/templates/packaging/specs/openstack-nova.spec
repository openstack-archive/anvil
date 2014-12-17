#encoding UTF-8
# Based on spec by:
# * Silas Sewell <silas@sewell.ch>
# * Andrey Brindeyev <abrindeyev@griddynamics.com>
# * Alessio Ababilov <aababilov@griddynamics.com>
# * Ivan A. Melnikov <imelnikov@griddynamics.com>

%global python_name nova
%global daemon_prefix openstack-nova
%global os_version ${version}
%global no_tests $no_tests
%global tests_data_dir %{_datarootdir}/%{python_name}-tests

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif


Name:             openstack-nova
Summary:          OpenStack Compute (nova)
Version:          %{os_version}$version_suffix
Release:          $release%{?dist}
Epoch:            $epoch

Group:            Development/Languages
License:          ASL 2.0
Vendor:           OpenStack Foundation
URL:              http://openstack.org/projects/compute/
Source0:          %{python_name}-%{os_version}.tar.gz

%if ! (0%{?rhel} > 6)
Source10:         openstack-nova-api.init
Source11:         openstack-nova-cert.init
Source12:         openstack-nova-compute.init
Source13:         openstack-nova-network.init
Source14:         openstack-nova-objectstore.init
Source15:         openstack-nova-scheduler.init
Source18:         openstack-nova-xvpvncproxy.init
Source19:         openstack-nova-console.init
Source20:         openstack-nova-consoleauth.init
Source25:         openstack-nova-metadata-api.init
Source26:         openstack-nova-conductor.init
Source27:         openstack-nova-cells.init
Source28:         openstack-nova-spicehtml5proxy.init
Source29:         openstack-nova-serialproxy.init
%else
Source10:         openstack-nova-api.service
Source11:         openstack-nova-cert.service
Source12:         openstack-nova-compute.service
Source13:         openstack-nova-network.service
Source14:         openstack-nova-objectstore.service
Source15:         openstack-nova-scheduler.service
Source18:         openstack-nova-xvpvncproxy.service
Source19:         openstack-nova-console.service
Source20:         openstack-nova-consoleauth.service
Source25:         openstack-nova-metadata-api.service
Source26:         openstack-nova-conductor.service
Source27:         openstack-nova-cells.service
Source28:         openstack-nova-spicehtml5proxy.service
Source29:         openstack-nova-serialproxy.service
%endif

Source50:         nova-ifc-template
Source51:         nova.logrotate
Source52:         nova-polkit.pkla
Source53:         nova-sudoers

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}

BuildArch:        noarch
BuildRequires:    python-devel
BuildRequires:    python-setuptools
BuildRequires:    python-pbr

Requires:         %{name}-compute = %{epoch}:%{version}-%{release}
Requires:         %{name}-cert = %{epoch}:%{version}-%{release}
Requires:         %{name}-scheduler = %{epoch}:%{version}-%{release}
Requires:         %{name}-api = %{epoch}:%{version}-%{release}
Requires:         %{name}-network = %{epoch}:%{version}-%{release}
Requires:         %{name}-objectstore = %{epoch}:%{version}-%{release}
Requires:         %{name}-console = %{epoch}:%{version}-%{release}

%description
OpenStack Compute (codename Nova) is open source software designed to
provision and manage large networks of virtual machines, creating a
redundant and scalable cloud computing platform. It gives you the
software, control panels, and APIs required to orchestrate a cloud,
including running instances, managing networks, and controlling access
through users and projects. OpenStack Compute strives to be both
hardware and hypervisor agnostic, currently supporting a variety of
standard hardware configurations and seven major hypervisors.

%package common
Summary:          Components common to all OpenStack services
Group:            Applications/System

Requires:         python-nova = %{epoch}:%{version}-%{release}

%if ! 0%{?usr_only}
Requires(post):   chkconfig
Requires(postun): initscripts
Requires(preun):  chkconfig
Requires(pre):    shadow-utils
%endif


%description common
OpenStack Compute (codename Nova) is open source software designed to
provision and manage large networks of virtual machines, creating a
redundant and scalable cloud computing platform. It gives you the
software, control panels, and APIs required to orchestrate a cloud,
including running instances, managing networks, and controlling access
through users and projects. OpenStack Compute strives to be both
hardware and hypervisor agnostic, currently supporting a variety of
standard hardware configurations and seven major hypervisors.

This package contains scripts, config and dependencies shared
between all the OpenStack nova services.

%package compute
Summary:          OpenStack Nova Virtual Machine control service
Group:            Applications/System

Requires:         %{name}-common = %{epoch}:%{version}-%{release}
Requires:         curl
Requires:         iscsi-initiator-utils
Requires:         iptables iptables-ipv6
Requires:         vconfig
# tunctl is needed where `ip tuntap` is not available
%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
Requires:         tunctl
%endif
Requires:         libguestfs-mount >= 1.7.17
# The fuse dependency should be added to libguestfs-mount
Requires:         fuse
Requires:         libvirt >= 0.8.7
Requires:         libvirt-python
Requires(pre):    qemu-kvm

%description compute
OpenStack Compute (codename Nova) is open source software designed to
provision and manage large networks of virtual machines, creating a
redundant and scalable cloud computing platform. It gives you the
software, control panels, and APIs required to orchestrate a cloud,
including running instances, managing networks, and controlling access
through users and projects. OpenStack Compute strives to be both
hardware and hypervisor agnostic, currently supporting a variety of
standard hardware configurations and seven major hypervisors.

This package contains the Nova service for controlling Virtual Machines.


%package network
Summary:          OpenStack Nova Network control service
Group:            Applications/System

Requires:         %{name}-common = %{epoch}:%{version}-%{release}
Requires:         vconfig
Requires:         radvd
Requires:         bridge-utils
Requires:         dnsmasq-utils
Requires:         dnsmasq
# tunctl is needed where `ip tuntap` is not available
%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
Requires:         tunctl
%endif

%description network
OpenStack Compute (codename Nova) is open source software designed to
provision and manage large networks of virtual machines, creating a
redundant and scalable cloud computing platform. It gives you the
software, control panels, and APIs required to orchestrate a cloud,
including running instances, managing networks, and controlling access
through users and projects. OpenStack Compute strives to be both
hardware and hypervisor agnostic, currently supporting a variety of
standard hardware configurations and seven major hypervisors.

This package contains the Nova service for controlling networking.


%package scheduler
Summary:          OpenStack Nova VM distribution service
Group:            Applications/System

Requires:         %{name}-common = %{epoch}:%{version}-%{release}

%description scheduler
OpenStack Compute (codename Nova) is open source software designed to
provision and manage large networks of virtual machines, creating a
redundant and scalable cloud computing platform. It gives you the
software, control panels, and APIs required to orchestrate a cloud,
including running instances, managing networks, and controlling access
through users and projects. OpenStack Compute strives to be both
hardware and hypervisor agnostic, currently supporting a variety of
standard hardware configurations and seven major hypervisors.

This package contains the service for scheduling where
to run Virtual Machines in the cloud.


%package cert
Summary:          OpenStack Nova certificate management service
Group:            Applications/System

Requires:         %{name}-common = %{epoch}:%{version}-%{release}

%description cert
OpenStack Compute (codename Nova) is open source software designed to
provision and manage large networks of virtual machines, creating a
redundant and scalable cloud computing platform. It gives you the
software, control panels, and APIs required to orchestrate a cloud,
including running instances, managing networks, and controlling access
through users and projects. OpenStack Compute strives to be both
hardware and hypervisor agnostic, currently supporting a variety of
standard hardware configurations and seven major hypervisors.

This package contains the Nova service for managing certificates.


%package api
Summary:          OpenStack Nova API services
Group:            Applications/System

Requires:         %{name}-common = %{epoch}:%{version}-%{release}

%description api
OpenStack Compute (codename Nova) is open source software designed to
provision and manage large networks of virtual machines, creating a
redundant and scalable cloud computing platform. It gives you the
software, control panels, and APIs required to orchestrate a cloud,
including running instances, managing networks, and controlling access
through users and projects. OpenStack Compute strives to be both
hardware and hypervisor agnostic, currently supporting a variety of
standard hardware configurations and seven major hypervisors.

This package contains the Nova services providing programmatic access.


%package conductor
Summary:          OpenStack Nova Conductor services
Group:            Applications/System

Requires:         openstack-nova-common = %{epoch}:%{version}-%{release}

%description conductor
OpenStack Compute (codename Nova) is open source software designed to
provision and manage large networks of virtual machines, creating a
redundant and scalable cloud computing platform. It gives you the
software, control panels, and APIs required to orchestrate a cloud,
including running instances, managing networks, and controlling access
through users and projects. OpenStack Compute strives to be both
hardware and hypervisor agnostic, currently supporting a variety of
standard hardware configurations and seven major hypervisors.

This package contains the Nova services providing database access for
the compute service


%package objectstore
Summary:          OpenStack Nova simple object store service
Group:            Applications/System

Requires:         %{name}-common = %{epoch}:%{version}-%{release}

%description objectstore
OpenStack Compute (codename Nova) is open source software designed to
provision and manage large networks of virtual machines, creating a
redundant and scalable cloud computing platform. It gives you the
software, control panels, and APIs required to orchestrate a cloud,
including running instances, managing networks, and controlling access
through users and projects. OpenStack Compute strives to be both
hardware and hypervisor agnostic, currently supporting a variety of
standard hardware configurations and seven major hypervisors.

This package contains the Nova service providing a simple object store.


%package console
Summary:          OpenStack Nova console access services
Group:            Applications/System

Requires:         %{name}-common = %{epoch}:%{version}-%{release}

%description console
OpenStack Compute (codename Nova) is open source software designed to
provision and manage large networks of virtual machines, creating a
redundant and scalable cloud computing platform. It gives you the
software, control panels, and APIs required to orchestrate a cloud,
including running instances, managing networks, and controlling access
through users and projects. OpenStack Compute strives to be both
hardware and hypervisor agnostic, currently supporting a variety of
standard hardware configurations and seven major hypervisors.

This package contains the Nova services providing console access
services to Virtual Machines.


%package cells
Summary:          OpenStack Nova Cells services
Group:            Applications/System

Requires:         openstack-nova-common = %{epoch}:%{version}-%{release}

%description cells
OpenStack Compute (codename Nova) is open source software designed to
provision and manage large networks of virtual machines, creating a
redundant and scalable cloud computing platform. It gives you the
software, control panels, and APIs required to orchestrate a cloud,
including running instances, managing networks, and controlling access
through users and projects. OpenStack Compute strives to be both
hardware and hypervisor agnostic, currently supporting a variety of
standard hardware configurations and seven major hypervisors.

This package contains the Nova Cells service providing additional
scaling and (geographic) distribution for compute services.

#if $newer_than_eq('2014.2')
%package serialproxy
Summary:          OpenStack Nova serial console access service
Group:            Applications/System

Requires:         openstack-nova-common = %{epoch}:%{version}-%{release}

%description serialproxy
OpenStack Compute (codename Nova) is open source software designed to
provision and manage large networks of virtual machines, creating a
redundant and scalable cloud computing platform. It gives you the
software, control panels, and APIs required to orchestrate a cloud,
including running instances, managing networks, and controlling access
through users and projects. OpenStack Compute strives to be both
hardware and hypervisor agnostic, currently supporting a variety of
standard hardware configurations and seven major hypervisors.

This package contains the Nova services providing the
serial console access service to Virtual Machines.
#end if

%package -n       python-nova
Summary:          Nova Python libraries
Group:            Applications/System

Requires:         openssl
Requires:         sudo
#for $i in $requires
Requires:         ${i}
#end for

%description -n   python-nova
OpenStack Compute (codename Nova) is open source software designed to
provision and manage large networks of virtual machines, creating a
redundant and scalable cloud computing platform.

This package contains the %{name} Python library.


%if ! 0%{?no_tests}
%package -n python-%{python_name}-tests
Summary:          Tests for Nova
Group:            Development/Libraries

# Bring in all subpackages:
Requires:         %{name} = %{epoch}:%{version}-%{release}
Requires:         %{name}-common = %{epoch}:%{version}-%{release}
Requires:         %{name}-compute = %{epoch}:%{version}-%{release}
Requires:         %{name}-network = %{epoch}:%{version}-%{release}
Requires:         %{name}-scheduler = %{epoch}:%{version}-%{release}
Requires:         %{name}-cert = %{epoch}:%{version}-%{release}
Requires:         %{name}-api = %{epoch}:%{version}-%{release}
Requires:         %{name}-conductor = %{epoch}:%{version}-%{release}
Requires:         %{name}-objectstore = %{epoch}:%{version}-%{release}
Requires:         %{name}-console = %{epoch}:%{version}-%{release}
Requires:         %{name}-cells = %{epoch}:%{version}-%{release}
#if $newer_than_eq('2014.2')
Requires:         %{name}-serialproxy = %{epoch}:%{version}-%{release}
#end if
Requires:         python-%{python_name} = %{epoch}:%{version}-%{release}

# Test requirements:
#for $i in $test_requires
Requires:         ${i}
#end for

%description -n python-%{python_name}-tests
Nova is a cloud computing fabric controller (the main part
of an IaaS system).

This package contains unit and functional tests for Nova, with
simple runner (%{python_name}-make-test-env).
%endif


%if 0%{?with_doc}
%package doc
Summary:          Documentation for %{name}
Group:            Documentation

BuildRequires:    python-sphinx

%description      doc
OpenStack Compute (codename Nova) is open source software designed to
provision and manage large networks of virtual machines, creating a
redundant and scalable cloud computing platform.

This package contains documentation files for %{name}.
%endif

%prep
%setup0 -q -n %{python_name}-%{os_version}
#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for

%build
%{__python} setup.py build

%install
rm -rf %{buildroot}
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

%if 0%{?with_doc}
#raw
export PYTHONPATH="$PWD:$PYTHONPATH"
pushd doc
sphinx-build -b html source build/html
popd
#end raw
# Fix hidden-file-or-dir warnings
rm -fr doc/build/html/.doctrees doc/build/html/.buildinfo
%endif

%if ! 0%{?usr_only}
# Setup directories
install -d -m 755 %{buildroot}%{_sharedstatedir}/nova
install -d -m 755 %{buildroot}%{_sharedstatedir}/nova/buckets
install -d -m 755 %{buildroot}%{_sharedstatedir}/nova/images
install -d -m 755 %{buildroot}%{_sharedstatedir}/nova/instances
install -d -m 755 %{buildroot}%{_sharedstatedir}/nova/keys
install -d -m 755 %{buildroot}%{_sharedstatedir}/nova/networks
install -d -m 755 %{buildroot}%{_sharedstatedir}/nova/tmp
install -d -m 755 %{buildroot}%{_localstatedir}/log/nova
install -d -m 755 %{buildroot}%{_localstatedir}/lock/nova

# Setup ghost CA cert
install -d -m 755 %{buildroot}%{_sharedstatedir}/nova/CA
install -p -m 755 nova/CA/*.sh %{buildroot}%{_sharedstatedir}/nova/CA
install -p -m 644 nova/CA/openssl.cnf.tmpl %{buildroot}%{_sharedstatedir}/nova/CA
install -d -m 755 %{buildroot}%{_sharedstatedir}/nova/CA/{certs,crl,newcerts,projects,reqs}
touch %{buildroot}%{_sharedstatedir}/nova/CA/{cacert.pem,crl.pem,index.txt,openssl.cnf,serial}
install -d -m 750 %{buildroot}%{_sharedstatedir}/nova/CA/private
touch %{buildroot}%{_sharedstatedir}/nova/CA/private/cakey.pem

# Clean CA directory
find %{buildroot}%{_sharedstatedir}/nova/CA -name .gitignore -delete
find %{buildroot}%{_sharedstatedir}/nova/CA -name .placeholder -delete

# Install config files
install -d -m 755 %{buildroot}%{_sysconfdir}/nova
#raw
for i in etc/nova/*; do
    if [ -f $i ] ; then
        install -p -D -m 640 $i  %{buildroot}%{_sysconfdir}/nova/
    fi
done
#end raw
# Install initscripts for Nova services
%if ! (0%{?rhel} > 6)
install -p -D -m 755 %{SOURCE10} %{buildroot}%{_initrddir}/%{daemon_prefix}-api
install -p -D -m 755 %{SOURCE11} %{buildroot}%{_initrddir}/%{daemon_prefix}-cert
install -p -D -m 755 %{SOURCE12} %{buildroot}%{_initrddir}/%{daemon_prefix}-compute
install -p -D -m 755 %{SOURCE13} %{buildroot}%{_initrddir}/%{daemon_prefix}-network
install -p -D -m 755 %{SOURCE14} %{buildroot}%{_initrddir}/%{daemon_prefix}-objectstore
install -p -D -m 755 %{SOURCE15} %{buildroot}%{_initrddir}/%{daemon_prefix}-scheduler
install -p -D -m 755 %{SOURCE18} %{buildroot}%{_initrddir}/%{daemon_prefix}-xvpvncproxy
install -p -D -m 755 %{SOURCE19} %{buildroot}%{_initrddir}/%{daemon_prefix}-console
install -p -D -m 755 %{SOURCE20} %{buildroot}%{_initrddir}/%{daemon_prefix}-consoleauth
install -p -D -m 755 %{SOURCE25} %{buildroot}%{_initrddir}/%{daemon_prefix}-metadata-api
install -p -D -m 755 %{SOURCE26} %{buildroot}%{_initrddir}/%{daemon_prefix}-conductor
install -p -D -m 755 %{SOURCE27} %{buildroot}%{_initrddir}/%{daemon_prefix}-cells
install -p -D -m 755 %{SOURCE28} %{buildroot}%{_initrddir}/%{daemon_prefix}-spicehtml5proxy
#if $newer_than_eq('2014.2')
install -p -D -m 755 %{SOURCE29} %{buildroot}%{_initrddir}/%{daemon_prefix}-serialproxy
#end if

#raw
#fix metadata-api bin name
sed -i s?exec=\"/usr/bin/nova-metadata-api\"?exec=\"/usr/bin/nova-api-metadata\"? %{buildroot}%{_initrddir}/%{daemon_prefix}-metadata-api
#end raw
%else
install -p -D -m 755 %{SOURCE10} %{buildroot}%{_unitdir}/%{daemon_prefix}-api.service
install -p -D -m 755 %{SOURCE11} %{buildroot}%{_unitdir}/%{daemon_prefix}-cert.service
install -p -D -m 755 %{SOURCE12} %{buildroot}%{_unitdir}/%{daemon_prefix}-compute.service
install -p -D -m 755 %{SOURCE13} %{buildroot}%{_unitdir}/%{daemon_prefix}-network.service
install -p -D -m 755 %{SOURCE14} %{buildroot}%{_unitdir}/%{daemon_prefix}-objectstore.service
install -p -D -m 755 %{SOURCE15} %{buildroot}%{_unitdir}/%{daemon_prefix}-scheduler.service
install -p -D -m 755 %{SOURCE18} %{buildroot}%{_unitdir}/%{daemon_prefix}-xvpvncproxy.service
install -p -D -m 755 %{SOURCE19} %{buildroot}%{_unitdir}/%{daemon_prefix}-console.service
install -p -D -m 755 %{SOURCE20} %{buildroot}%{_unitdir}/%{daemon_prefix}-consoleauth.service
install -p -D -m 755 %{SOURCE25} %{buildroot}%{_unitdir}/%{daemon_prefix}-metadata-api.service
install -p -D -m 755 %{SOURCE26} %{buildroot}%{_unitdir}/%{daemon_prefix}-conductor.service
install -p -D -m 755 %{SOURCE27} %{buildroot}%{_unitdir}/%{daemon_prefix}-cells.service
install -p -D -m 755 %{SOURCE28} %{buildroot}%{_unitdir}/%{daemon_prefix}-spicehtml5proxy.service
#if $newer_than_eq('2014.2')
install -p -D -m 755 %{SOURCE29} %{buildroot}%{_unitdir}/%{daemon_prefix}-serialproxy.service
#end if
%endif

# Install sudoers
install -p -D -m 440 %{SOURCE53} %{buildroot}%{_sysconfdir}/sudoers.d/nova

# Install logrotate
install -p -D -m 644 %{SOURCE51} %{buildroot}%{_sysconfdir}/logrotate.d/%{name}

# Install pid directory
install -d -m 755 %{buildroot}%{_localstatedir}/run/nova

install -d -m 755 %{buildroot}%{_sysconfdir}/polkit-1/localauthority/50-local.d
install -p -D -m 644 %{SOURCE52} %{buildroot}%{_sysconfdir}/polkit-1/localauthority/50-local.d/50-nova.pkla
%endif

# Install template files
install -p -D -m 644 nova/cloudpipe/client.ovpn.template %{buildroot}%{_datarootdir}/nova/client.ovpn.template
install -p -D -m 644 nova/virt/interfaces.template %{buildroot}%{_datarootdir}/nova/interfaces.template

# Install rootwrap files in /usr/share/nova/rootwrap
mkdir -p %{buildroot}%{_datarootdir}/nova/rootwrap/
install -p -D -m 644 etc/nova/rootwrap.d/* %{buildroot}%{_datarootdir}/nova/rootwrap/

# Network configuration templates for injection engine
install -d -m 755 %{buildroot}%{_datarootdir}/nova/interfaces/
install -p -D -m 644 nova/virt/interfaces.template %{buildroot}%{_datarootdir}/nova/interfaces/interfaces.ubuntu.template
install -p -D -m 644 %{SOURCE50} %{buildroot}%{_datarootdir}/nova/interfaces.template

# Remove unneeded in production stuff
rm -f %{buildroot}%{_bindir}/nova-debug
rm -fr %{buildroot}%{python_sitelib}/run_tests.*
rm -f %{buildroot}%{_bindir}/nova-combined
rm -f %{buildroot}/usr/share/doc/nova/README*

# We currently use the equivalent file from the novnc package
rm -f %{buildroot}%{_bindir}/nova-novncproxy

%if ! 0%{?no_tests}
#include $part_fn("install_tests.sh")
%endif

%clean
rm -rf %{buildroot}


%post
if %{_sbindir}/selinuxenabled; then
    echo -e "\033[47m\033[1;31m***************************************************\033[0m"
    echo -e "\033[47m\033[1;31m*\033[0m \033[40m\033[1;31m                                                \033[47m\033[1;31m*\033[0m"
    echo -e "\033[47m\033[1;31m*\033[0m \033[40m\033[1;31m >> \033[5mYou have SELinux enabled on your host !\033[25m <<  \033[47m\033[1;31m*\033[0m"
    echo -e "\033[47m\033[1;31m*\033[0m \033[40m\033[1;31m                                                \033[47m\033[1;31m*\033[0m"
    echo -e "\033[47m\033[1;31m*\033[0m \033[40m\033[1;31mPlease disable it by setting \`SELINUX=disabled' \033[47m\033[1;31m*\033[0m"
    echo -e "\033[47m\033[1;31m*\033[0m \033[40m\033[1;31min /etc/sysconfig/selinux and don't forget      \033[47m\033[1;31m*\033[0m"
    echo -e "\033[47m\033[1;31m*\033[0m \033[40m\033[1;31mto reboot your host to apply that change!       \033[47m\033[1;31m*\033[0m"
    echo -e "\033[47m\033[1;31m*\033[0m \033[40m\033[1;31m                                                \033[47m\033[1;31m*\033[0m"
    echo -e "\033[47m\033[1;31m***************************************************\033[0m"
fi


%if ! 0%{?usr_only}
%pre common
getent group nova >/dev/null || groupadd -r nova
getent passwd nova >/dev/null || \
useradd -r -g nova -d %{_sharedstatedir}/nova -s /sbin/nologin \
-c "OpenStack Nova Daemons" nova
exit 0

%pre compute
usermod -a -G qemu nova
# Add nova to the fuse group (if present) to support guestmount
if getent group fuse >/dev/null; then
  usermod -a -G fuse nova
fi
exit 0

# Do not autostart daemons in %post since they are not configured yet

#if $older_than('2014.2')
#set $daemon_map = {"api": ["api", "metadata-api"], "cells": [], "cert": [], "compute": [], "console": ["console", "consoleauth", "xvpvncproxy"], "network": [], "objectstore": [], "scheduler": []}
#else
#set $daemon_map = {"api": ["api", "metadata-api"], "cells": [], "cert": [], "compute": [], "console": ["console", "consoleauth", "xvpvncproxy", "serialproxy"], "network": [], "objectstore": [], "scheduler": []}
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

%postun $key
if [ \$1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    for svc in $daemon_list; do
%if ! (0%{?rhel} > 6)
        /sbin/service %{daemon_prefix}-\${svc} condrestart &>/dev/null
%else
        /usr/bin/systemctl try-restart %{daemon_prefix}-\${svc}.service #>/dev/null 2>&1 || :
%endif
    done
    exit 0
fi
#end for
%endif

%files
%doc README* LICENSE* HACKING* ChangeLog AUTHORS
%{_bindir}/nova-all

%files common
%doc LICENSE

%if ! 0%{?usr_only}
%dir %{_sysconfdir}/nova
%config(noreplace) %attr(-, root, nova) %{_sysconfdir}/nova/*
%config(noreplace) %{_sysconfdir}/logrotate.d/openstack-nova
%config(noreplace) %{_sysconfdir}/sudoers.d/nova
%config(noreplace) %{_sysconfdir}/polkit-1/localauthority/50-local.d/50-nova.pkla

%dir %attr(0755, nova, root) %{_localstatedir}/log/nova
%dir %attr(0755, nova, root) %{_localstatedir}/lock/nova
%dir %attr(0755, nova, root) %{_localstatedir}/run/nova
%endif

#if $older_than_eq('2014.1.99999')
%{_bindir}/nova-clear-rabbit-queues
#end if

%{_bindir}/nova-manage
%{_bindir}/nova-rootwrap

#if $older_than('2014.1')
%{_bindir}/nova-rpc-zmq-receiver
#end if

%{_datarootdir}/nova
#%{_mandir}/man1/nova*.1.gz

%if ! 0%{?usr_only}
%defattr(-, nova, nova, -)
%dir %{_sharedstatedir}/nova
%dir %{_sharedstatedir}/nova/buckets
%dir %{_sharedstatedir}/nova/images
%dir %{_sharedstatedir}/nova/instances
%dir %{_sharedstatedir}/nova/keys
%dir %{_sharedstatedir}/nova/networks
%dir %{_sharedstatedir}/nova/tmp
%endif


%files compute
%{_bindir}/nova-compute
%{_bindir}/nova-baremetal-deploy-helper
%{_bindir}/nova-baremetal-manage
%{_bindir}/nova-idmapshift
%{_datarootdir}/nova/rootwrap/compute.filters

%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-compute
%else
%{_unitdir}/%{daemon_prefix}-compute.service
%endif
%endif


%files network
%{_bindir}/nova-network
%{_bindir}/nova-dhcpbridge
%{_datarootdir}/nova/rootwrap/network.filters

%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-network
%else
%{_unitdir}/%{daemon_prefix}-network.service
%endif
%endif


%files scheduler
%{_bindir}/nova-scheduler

%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-scheduler
%else
%{_unitdir}/%{daemon_prefix}-scheduler.service
%endif
%endif


%files cert
%{_bindir}/nova-cert
%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-cert
%else
%{_unitdir}/%{daemon_prefix}-cert.service
%endif
%defattr(-, nova, nova, -)
%dir %{_sharedstatedir}/nova/CA/
%dir %{_sharedstatedir}/nova/CA/certs
%dir %{_sharedstatedir}/nova/CA/crl
%dir %{_sharedstatedir}/nova/CA/newcerts
%dir %{_sharedstatedir}/nova/CA/projects
%dir %{_sharedstatedir}/nova/CA/reqs
%{_sharedstatedir}/nova/CA/*.sh
%{_sharedstatedir}/nova/CA/openssl.cnf.tmpl
%ghost %config(missingok,noreplace) %verify(not md5 size mtime) %{_sharedstatedir}/nova/CA/cacert.pem
%ghost %config(missingok,noreplace) %verify(not md5 size mtime) %{_sharedstatedir}/nova/CA/crl.pem
%ghost %config(missingok,noreplace) %verify(not md5 size mtime) %{_sharedstatedir}/nova/CA/index.txt
%ghost %config(missingok,noreplace) %verify(not md5 size mtime) %{_sharedstatedir}/nova/CA/openssl.cnf
%ghost %config(missingok,noreplace) %verify(not md5 size mtime) %{_sharedstatedir}/nova/CA/serial
%dir %attr(0750, -, -) %{_sharedstatedir}/nova/CA/private
%ghost %config(missingok,noreplace) %verify(not md5 size mtime) %{_sharedstatedir}/nova/CA/private/cakey.pem
%endif


%files api
%{_bindir}/nova-api*
%{_datarootdir}/nova/rootwrap/api-metadata.filters

%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/openstack-nova-*api
%else
%{_unitdir}/%{daemon_prefix}-*api.service
%endif
%endif


%files conductor
%{_bindir}/nova-conductor

%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/openstack-nova-conductor
%else
%{_unitdir}/%{daemon_prefix}-conductor.service
%endif
%endif


%files objectstore
%{_bindir}/nova-objectstore
%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-objectstore
%else
%{_unitdir}/%{daemon_prefix}-objectstore.service
%endif
%endif


%files console
%{_bindir}/nova-console*
%{_bindir}/nova-xvpvncproxy
%{_bindir}/nova-spicehtml5proxy

%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/openstack-nova-console*
%{_initrddir}/openstack-nova-xvpvncproxy
%{_initrddir}/openstack-nova-spicehtml5proxy
%else
%{_unitdir}/%{daemon_prefix}-console*.service
%{_unitdir}/%{daemon_prefix}-xvpvncproxy.service
%{_unitdir}/%{daemon_prefix}-spicehtml5proxy.service
%endif
%endif

#if $newer_than_eq('2014.2')
%files serialproxy
%{_bindir}/nova-serialproxy

%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{daemon_prefix}-serialproxy
%else
%{_unitdir}/%{daemon_prefix}-serialproxy.service
%endif
%endif
#end if

%files cells
%{_bindir}/nova-cells

%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/openstack-nova-cells
%else
%{_unitdir}/%{daemon_prefix}-cells.service
%endif
%endif

%files -n python-nova
%defattr(-,root,root,-)
%doc LICENSE
%{python_sitelib}/nova
%exclude %{python_sitelib}/%{python_name}/tests
%{python_sitelib}/nova-%{os_version}-*.egg-info

%if ! 0%{?no_tests}
%files -n python-%{python_name}-tests
%{tests_data_dir}
%{_bindir}/%{python_name}-make-test-env
%endif

%if 0%{?with_doc}
%files doc
%doc LICENSE doc/build/html
%endif

%changelog

