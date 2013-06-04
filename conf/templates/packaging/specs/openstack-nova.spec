%global python_name nova
%global daemon_prefix openstack-nova

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

Name:             openstack-nova
Summary:          OpenStack Compute (nova)
Version:          $version
Release:          1%{?dist}
Epoch:            $epoch

Group:            Development/Languages
License:          ASL 2.0
Vendor:           OpenStack Foundation
URL:              http://openstack.org/projects/compute/
Source0:          %{python_name}-%{version}.tar.gz

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

Source50:         nova-ifc-template
Source51:         nova.logrotate
Source52:         nova-polkit.pkla
Source53:         nova-sudoers

BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}

BuildArch:        noarch
BuildRequires:    python-devel
BuildRequires:    python-setuptools
BuildRequires:    intltool

Requires:         %{name}-compute = %{epoch}:%{version}-%{release}
Requires:         %{name}-cert = %{epoch}:%{version}-%{release}
Requires:         %{name}-scheduler = %{epoch}:%{version}-%{release}
Requires:         %{name}-api = %{epoch}:%{version}-%{release}
Requires:         %{name}-network = %{epoch}:%{version}-%{release}
Requires:         %{name}-objectstore = %{epoch}:%{version}-%{release}
Requires:         %{name}-console = %{epoch}:%{version}-%{release}

%description
Nova is a cloud computing fabric controller (the main part of an IaaS system)
built to match the popular AWS EC2 and S3 APIs. It is written in Python, using
the Tornado and Twisted frameworks, and relies on the standard AMQP messaging
protocol, and the Redis KVS.

Nova is intended to be easy to extend, and adapt. For example, it currently
uses an LDAP server for users and groups, but also includes a fake LDAP server,
that stores data in Redis. It has extensive test coverage, and uses the Sphinx
toolkit (the same as Python itself) for code and user documentation.

%package common
Summary:          Components common to all OpenStack services
Group:            Applications/System

Requires:         python-nova = %{epoch}:%{version}-%{release}

Requires(post):   chkconfig
Requires(postun): initscripts
Requires(preun):  chkconfig
Requires(pre):    shadow-utils


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
Requires:         tunctl
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
#TODO: Enable when available in RHEL 6.3
#Requires:         dnsmasq-utils
Requires:         dnsmasq
# tunctl is needed where `ip tuntap` is not available
Requires:         tunctl

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

This package contains the Nova services providing
console access services to Virtual Machines.


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


%package -n       python-nova
Summary:          Nova Python libraries
Group:            Applications/System

Requires:         openssl
Requires:         sudo

#for $i in $requires
${i}
#end for

%description -n   python-nova
Nova is a cloud computing fabric controller (the main part of an IaaS system)
built to match the popular AWS EC2 and S3 APIs. It is written in Python, using
the Tornado and Twisted frameworks, and relies on the standard AMQP messaging
protocol, and the Redis KVS.

This package contains the %{name} Python library.

%if 0%{?with_doc}

%package doc
Summary:          Documentation for %{name}
Group:            Documentation

BuildRequires:    python-sphinx

%description      doc
Nova is a cloud computing fabric controller (the main part of an IaaS system)
built to match the popular AWS EC2 and S3 APIs. It is written in Python, using
the Tornado and Twisted frameworks, and relies on the standard AMQP messaging
protocol, and the Redis KVS.

This package contains documentation files for %{name}.
%endif

#raw
%prep
%setup0 -q -n %{python_name}-%{version}

%build
%{__python} setup.py build

%install
rm -rf %{buildroot}
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

%if 0%{?with_doc}
export PYTHONPATH="$( pwd ):$PYTHONPATH"
pushd doc
sphinx-build -b html source build/html
popd

# Fix hidden-file-or-dir warnings
rm -fr doc/build/html/.doctrees doc/build/html/.buildinfo
%endif

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

# Install config files
install -d -m 755 %{buildroot}%{_sysconfdir}/nova
install -p -D -m 640 etc/nova/api-paste.ini %{buildroot}%{_sysconfdir}/nova/api-paste.ini
install -p -D -m 640 etc/nova/policy.json %{buildroot}%{_sysconfdir}/nova/policy.json

install -p -D -m 640 etc/nova/nova.conf.sample %{buildroot}%{_sysconfdir}/nova/nova.conf.sample

# Install initscripts for Nova services
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

# Install sudoers
install -p -D -m 440 %{SOURCE53} %{buildroot}%{_sysconfdir}/sudoers.d/nova

# Install logrotate
install -p -D -m 644 %{SOURCE51} %{buildroot}%{_sysconfdir}/logrotate.d/%{name}

# Install pid directory
install -d -m 755 %{buildroot}%{_localstatedir}/run/nova

# Install template files
install -p -D -m 644 nova/cloudpipe/client.ovpn.template %{buildroot}%{_datarootdir}/nova/client.ovpn.template
install -p -D -m 644 nova/virt/interfaces.template %{buildroot}%{_datarootdir}/nova/interfaces.template

# Install rootwrap files in /usr/share/nova/rootwrap
mkdir -p %{buildroot}%{_datarootdir}/nova/rootwrap/
install -p -D -m 644 etc/nova/rootwrap.d/* %{buildroot}%{_datarootdir}/nova/rootwrap/

# Network configuration templates for injection engine
install -d -m 755 %{buildroot}%{_datarootdir}/nova/interfaces
#install -p -D -m 644 nova/virt/interfaces.template %{buildroot}%{_datarootdir}/nova/interfaces/interfaces.ubuntu.template
install -p -D -m 644 %{SOURCE50} %{buildroot}%{_datarootdir}/nova/interfaces.template

# Clean CA directory
find %{buildroot}%{_sharedstatedir}/nova/CA -name .gitignore -delete
find %{buildroot}%{_sharedstatedir}/nova/CA -name .placeholder -delete

install -d -m 755 %{buildroot}%{_sysconfdir}/polkit-1/localauthority/50-local.d
install -p -D -m 644 %{SOURCE52} %{buildroot}%{_sysconfdir}/polkit-1/localauthority/50-local.d/50-nova.pkla

# Remove unneeded in production stuff
rm -f %{buildroot}%{_bindir}/nova-debug
rm -fr %{buildroot}%{python_sitelib}/nova/tests/
rm -fr %{buildroot}%{python_sitelib}/run_tests.*
rm -f %{buildroot}%{_bindir}/nova-combined
rm -f %{buildroot}/usr/share/doc/nova/README*

# We currently use the equivalent file from the novnc package
rm -f %{buildroot}%{_bindir}/nova-novncproxy

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

%pre common
getent group nova >/dev/null || groupadd -r nova --gid 162
if ! getent passwd nova >/dev/null; then
  useradd -u 162 -r -g nova -G nova,nobody -d %{_sharedstatedir}/nova -s /sbin/nologin -c "OpenStack Nova Daemons" nova
fi
exit 0

%pre compute
usermod -a -G qemu nova
# Add nova to the fuse group (if present) to support guestmount
if getent group fuse >/dev/null; then
  usermod -a -G fuse nova
fi
exit 0

%post compute
if [ $1 -eq 1 ] ; then
    # Initial installation
    /sbin/chkconfig --add %{daemon_prefix}-compute
fi
%post network
if [ $1 -eq 1 ] ; then
    # Initial installation
    /sbin/chkconfig --add %{daemon_prefix}-network
fi
%post scheduler
if [ $1 -eq 1 ] ; then
    # Initial installation
    /sbin/chkconfig --add %{daemon_prefix}-scheduler
fi
%post cert
if [ $1 -eq 1 ] ; then
    # Initial installation
    /sbin/chkconfig --add %{daemon_prefix}-cert
fi
%post api
if [ $1 -eq 1 ] ; then
    # Initial installation
    for svc in api metadata-api; do
        /sbin/chkconfig --add %{daemon_prefix}-$svc
    done
fi
%post conductor
if [ $1 -eq 1 ] ; then
    # Initial installation
    /sbin/chkconfig --add %{daemon_prefix}-conductor
fi
%post objectstore
if [ $1 -eq 1 ] ; then
    # Initial installation
    /sbin/chkconfig --add %{daemon_prefix}-objectstore
fi
%post console
if [ $1 -eq 1 ] ; then
    # Initial installation
    for svc in console consoleauth xvpvncproxy; do
        /sbin/chkconfig --add %{daemon_prefix}-svc
    done
fi
%post cells
if [ $1 -eq 1 ] ; then
    # Initial installation
    /sbin/chkconfig --add %{daemon_prefix}-cells
fi

%preun compute
if [ $1 -eq 0 ] ; then
    for svc in compute; do
        /sbin/service %{daemon_prefix}-${svc} stop >/dev/null 2>&1
        /sbin/chkconfig --del %{daemon_prefix}-${svc}
    done
fi
%preun network
if [ $1 -eq 0 ] ; then
    for svc in network; do
        /sbin/service %{daemon_prefix}-${svc} stop >/dev/null 2>&1
        /sbin/chkconfig --del %{daemon_prefix}-${svc}
    done
fi
%preun scheduler
if [ $1 -eq 0 ] ; then
    for svc in scheduler; do
        /sbin/service %{daemon_prefix}-${svc} stop >/dev/null 2>&1
        /sbin/chkconfig --del %{daemon_prefix}-${svc}
    done
fi
%preun cert
if [ $1 -eq 0 ] ; then
    for svc in cert; do
        /sbin/service %{daemon_prefix}-${svc} stop >/dev/null 2>&1
        /sbin/chkconfig --del %{daemon_prefix}-${svc}
    done
fi
%preun api
if [ $1 -eq 0 ] ; then
    for svc in api metadata-api; do
        /sbin/service %{daemon_prefix}-${svc} stop >/dev/null 2>&1
        /sbin/chkconfig --del %{daemon_prefix}-${svc}
    done
fi
%preun objectstore
if [ $1 -eq 0 ] ; then
    for svc in objectstore; do
        /sbin/service %{daemon_prefix}-${svc} stop >/dev/null 2>&1
        /sbin/chkconfig --del %{daemon_prefix}-${svc}
    done
fi
%preun console
if [ $1 -eq 0 ] ; then
    for svc in console consoleauth xvpvncproxy; do
        /sbin/chkconfig --add %{daemon_prefix}-svc
        /sbin/service %{daemon_prefix}-${svc} stop >/dev/null 2>&1
        /sbin/chkconfig --del %{daemon_prefix}-${svc}
    done
fi
%preun cells
if [ $1 -eq 0 ] ; then
    /sbin/service %{daemon_prefix}-cells stop >/dev/null 2>&1
    /sbin/chkconfig --del %{daemon_prefix}-cells
fi


%postun compute
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    for svc in compute; do
        /sbin/service %{daemon_prefix}-${svc} condrestart > /dev/null 2>&1 || :
    done
fi
%postun network
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    for svc in network; do
        /sbin/service %{daemon_prefix}-${svc} condrestart > /dev/null 2>&1 || :
    done
fi
%postun scheduler
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    for svc in scheduler; do
        /sbin/service %{daemon_prefix}-${svc} condrestart > /dev/null 2>&1 || :
    done
fi
%postun cert
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    for svc in cert; do
        /sbin/service %{daemon_prefix}-${svc} condrestart > /dev/null 2>&1 || :
    done
fi
%postun api
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    for svc in api direct-api metadata-api; do
        /sbin/service %{daemon_prefix}-${svc} condrestart > /dev/null 2>&1 || :
    done
fi
%postun objectstore
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    for svc in objectstore; do
        /sbin/service %{daemon_prefix}-${svc} condrestart > /dev/null 2>&1 || :
    done
fi
%postun console
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    for svc in console consoleauth xvpvncproxy; do
        /sbin/service %{daemon_prefix}-${svc} condrestart > /dev/null 2>&1 || :
    done
fi

%files
%doc LICENSE
%{_bindir}/nova-all

%files common
%doc LICENSE
%dir %{_sysconfdir}/nova
%config(noreplace) %attr(-, root, nova) %{_sysconfdir}/nova/nova.conf.sample
%config(noreplace) %attr(-, root, nova) %{_sysconfdir}/nova/api-paste.ini
%config(noreplace) %attr(-, root, nova) %{_sysconfdir}/nova/policy.json
%config(noreplace) %{_sysconfdir}/logrotate.d/openstack-nova
%config(noreplace) %{_sysconfdir}/sudoers.d/nova
%config(noreplace) %{_sysconfdir}/polkit-1/localauthority/50-local.d/50-nova.pkla

%dir %attr(0755, nova, root) %{_localstatedir}/log/nova
%dir %attr(0755, nova, root) %{_localstatedir}/lock/nova
%dir %attr(0755, nova, root) %{_localstatedir}/run/nova

%{_bindir}/nova-clear-rabbit-queues
# TODO. zmq-receiver may need its own service?
%{_bindir}/nova-rpc-zmq-receiver
%{_bindir}/nova-manage
%{_bindir}/nova-rootwrap

%{_datarootdir}/nova
#%{_mandir}/man1/nova*.1.gz

%defattr(-, nova, nova, -)
%dir %{_sharedstatedir}/nova
%dir %{_sharedstatedir}/nova/buckets
%dir %{_sharedstatedir}/nova/images
%dir %{_sharedstatedir}/nova/instances
%dir %{_sharedstatedir}/nova/keys
%dir %{_sharedstatedir}/nova/networks
%dir %{_sharedstatedir}/nova/tmp

%files compute
%{_bindir}/nova-compute
%{_bindir}/nova-baremetal-deploy-helper
%{_bindir}/nova-baremetal-manage
%{_initrddir}/%{daemon_prefix}-compute
%{_datarootdir}/nova/rootwrap/compute.filters

%files network
%{_bindir}/nova-network
%{_bindir}/nova-dhcpbridge
%{_initrddir}/%{daemon_prefix}-network
%{_datarootdir}/nova/rootwrap/network.filters

%files scheduler
%{_bindir}/nova-scheduler
%{_initrddir}/%{daemon_prefix}-scheduler

%files cert
%{_bindir}/nova-cert
%{_initrddir}/%{daemon_prefix}-cert
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

%files api
%{_bindir}/nova-api*
%{_initrddir}/openstack-nova-*api
%{_datarootdir}/nova/rootwrap/api-metadata.filters

%files conductor
%{_bindir}/nova-conductor
%{_initrddir}/openstack-nova-conductor

%files objectstore
%{_bindir}/nova-objectstore
%{_initrddir}/%{daemon_prefix}-objectstore

%files console
%{_bindir}/nova-console*
%{_bindir}/nova-xvpvncproxy
%{_bindir}/nova-spicehtml5proxy
%{_initrddir}/openstack-nova-console*
%{_initrddir}/openstack-nova-xvpvncproxy
%{_initrddir}/openstack-nova-spicehtml5proxy

%files cells
%{_bindir}/nova-cells
%{_initrddir}/openstack-nova-cells

%files -n python-nova
%defattr(-,root,root,-)
%doc LICENSE
%{python_sitelib}/nova
%{python_sitelib}/nova-%{version}-*.egg-info

%if 0%{?with_doc}
%files doc
%doc LICENSE doc/build/html
%endif

%changelog
#end raw
