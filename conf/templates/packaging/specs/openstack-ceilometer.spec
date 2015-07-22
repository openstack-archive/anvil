%global _without_doc 1
%global with_doc %{!?_without_doc:1}%{?_without_doc:0}
%global python_name ceilometer
%global daemon_prefix openstack-ceilometer
%global os_version ${version}

Name:             openstack-ceilometer
Version:          %{os_version}$version_suffix
Release:          $release%{?dist}
Summary:          OpenStack measurement collection service

Group:            Applications/System
License:          ASL 2.0
URL:              https://wiki.openstack.org/wiki/Ceilometer
Source0:          %{python_name}-%{os_version}.tar.gz

%if ! (0%{?rhel} > 6)
Source10:         openstack-ceilometer-api.init
Source11:         openstack-ceilometer-collector.init
Source12:         openstack-ceilometer-compute.init
Source13:         openstack-ceilometer-central.init
Source14:         openstack-ceilometer-alarm-notifier.init
Source15:         openstack-ceilometer-alarm-evaluator.init
%else
Source10:         openstack-ceilometer-api.service
Source11:         openstack-ceilometer-collector.service
Source12:         openstack-ceilometer-compute.service
Source13:         openstack-ceilometer-central.service
Source14:         openstack-ceilometer-alarm-notifier.service
Source15:         openstack-ceilometer-alarm-evaluator.service
%endif
#if $newer_than_eq('2014.1')
%if ! (0%{?rhel} > 6)
Source16:         openstack-ceilometer-notification.init
%else
Source16:         openstack-ceilometer-notification.service
%endif
#end if
#if $newer_than_eq('2014.2')
%if ! (0%{?rhel} > 6)
Source17:         openstack-ceilometer-ipmi.init
%else
Source17:         openstack-ceilometer-ipmi.service
%endif
Source18:         ceilometer-rootwrap-sudoers
#end if
#if $newer_than_eq('2015.1')
%if ! (0%{?rhel} > 6)
Source19:         openstack-ceilometer-polling.init
%else
Source19:         openstack-ceilometer-polling.service
%endif
#end if

Source20:          ceilometer-dist.conf
Source21:          ceilometer.logrotate

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}

BuildArch:        noarch
BuildRequires:    intltool

#Rhel6 requires
%if ! (0%{?fedora} <= 12 || 0%{?rhel} <= 6)
BuildRequires:    python-sphinx10
# These are required to build due to the requirements check added
BuildRequires:    python-sqlalchemy0.7
%endif

#rhel7 requires
%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
BuildRequires:    python-sqlalchemy
%endif

BuildRequires:    python-setuptools
BuildRequires:    python-pbr
BuildRequires:    python-d2to1
BuildRequires:    python2-devel
#Rhel6 requires
%if ! (0%{?fedora} <= 12 || 0%{?rhel} <= 6)
BuildRequires:    python-webob1.2
%endif

#rhel7 requires
%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
BuildRequires:    python-webob
%endif

%description
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

%package -n       python-ceilometer
Summary:          OpenStack ceilometer python libraries
Group:            Applications/System

#for $i in $requires
Requires:         ${i}
#end for

#for $i in $conflicts
Conflicts:       ${i}
#end for

%description -n   python-ceilometer
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the ceilometer python library.

%package common
Summary:          Components common to all OpenStack ceilometer services
Group:            Applications/System

Requires:         python-ceilometer

Requires(pre):    shadow-utils

%description common
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains components common to all OpenStack
ceilometer services.

%package compute
Summary:          OpenStack ceilometer compute agent
Group:            Applications/System

Requires:         %{name}-common = %{version}-%{release}

Requires:         python-novaclient
Requires:         python-keystoneclient
Requires:         libvirt-python

%description compute
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the ceilometer agent for
running on OpenStack compute nodes.

%package central
Summary:          OpenStack ceilometer central agent
Group:            Applications/System

Requires:         %{name}-common = %{version}-%{release}

Requires:         python-novaclient
Requires:         python-keystoneclient
Requires:         python-glanceclient
Requires:         python-swiftclient

%description central
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the central ceilometer agent.

%package collector
Summary:          OpenStack ceilometer collector agent
Group:            Applications/System

Requires:         %{name}-common = %{version}-%{release}

Requires:         python-pymongo

%description collector
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the ceilometer collector agent.

%package api
Summary:          OpenStack ceilometer API service
Group:            Applications/System

Requires:         %{name}-common = %{version}-%{release}

Requires:         python-pymongo
Requires:         python-flask
Requires:         python-pecan
Requires:         python-wsme

%description api
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the ceilometer API service.

%package alarm
Summary:          OpenStack ceilometer alarm services
Group:            Applications/System

Requires:         %{name}-common = %{version}-%{release}
Requires:         python-ceilometerclient

%description alarm
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the ceilometer alarm notification
and evaluation services.

#if $newer_than_eq('2014.1')
%package notification
Summary:          OpenStack ceilometer notifier services
Group:            Applications/System

Requires:         %{name}-common = %{version}-%{release}
Requires:         python-ceilometerclient

%description notification
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the ceilometer alarm notification
and evaluation services.
#end if

#if $newer_than_eq('2014.2')
%package ipmi
Summary:          OpenStack ceilometer ipmi agent
Group:            Applications/System

Requires:         %{name}-common = %{version}-%{release}

Requires:         python-novaclient
Requires:         python-keystoneclient
Requires:         python-neutronclient
Requires:         python-tooz
Requires:         python-oslo-rootwrap
Requires:         ipmitool

%description ipmi
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the ipmi agent to be run on OpenStack
nodes from which IPMI sensor data is to be collected directly,
by-passing Ironic's management of baremetal.
#end if

#if $newer_than_eq('2015.1')
%package polling
Summary:          OpenStack ceilometer polling agent
Group:            Applications/System

Requires:         %{name}-common = %{version}-%{release}

%description polling
Ceilometer aims to deliver a unique point of contact for billing systems to
aquire all counters they need to establish customer billing, across all
current and future OpenStack components. The delivery of counters must
be tracable and auditable, the counters must be easily extensible to support
new projects, and agents doing data collections should be
independent of the overall system.

This package contains the polling service.
#end if

%if 0%{?with_doc}
%package doc
Summary:          Documentation for OpenStack ceilometer
Group:            Documentation

# Required to build module documents
BuildRequires:    python-eventlet
%if ! (0%{?fedora} <= 12 || 0%{?rhel} <= 6)
BuildRequires:    python-sqlalchemy0.7
%endif

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
BuildRequires:    python-sqlalchemy
%endif

BuildRequires:    python-webob
# while not strictly required, quiets the build down when building docs.
BuildRequires:    python-migrate
BuildRequires:    python-iso8601

%description      doc
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains documentation files for ceilometer.
%endif

%prep
%setup -q -n %{python_name}-%{os_version}

#raw
find . \( -name .gitignore -o -name .placeholder \) -delete

find ceilometer -name \*.py -exec sed -i '/\/usr\/bin\/env python/{d;q}' {} +

# TODO: Have the following handle multi line entries
sed -i '/setup_requires/d; /install_requires/d; /dependency_links/d' setup.py

#end raw
#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for

%build

export PBR_VERSION=$version
%{__python} setup.py build

%install

export PBR_VERSION=$version
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

#raw
# docs generation requires everything to be installed first
export PYTHONPATH="$( pwd ):$PYTHONPATH"

pushd doc

%if 0%{?with_doc}
SPHINX_DEBUG=1 sphinx-1.0-build -b html source build/html
# Fix hidden-file-or-dir warnings
rm -fr build/html/.doctrees build/html/.buildinfo
%endif

popd
#end raw

# Setup directories
install -d -m 755 %{buildroot}%{_sharedstatedir}/ceilometer
install -d -m 755 %{buildroot}%{_sharedstatedir}/ceilometer/tmp
install -d -m 755 %{buildroot}%{_localstatedir}/log/ceilometer
#if $newer_than_eq('2014.2')
install -d -m 755 %{buildroot}%{_sharedstatedir}/ceilometer/rootwrap.d
#end if

# Install config files
install -d -m 755 %{buildroot}%{_sysconfdir}/ceilometer
#if $older_than('2014.2')
install -p -D -m 640 %{SOURCE20} %{buildroot}%{_datadir}/ceilometer/ceilometer-dist.conf
install -p -D -m 640 etc/ceilometer/ceilometer.conf.sample %{buildroot}%{_sysconfdir}/ceilometer/ceilometer.conf

install -p -D -m 640 etc/ceilometer/policy.json %{buildroot}%{_sysconfdir}/ceilometer/policy.json
install -p -D -m 640 etc/ceilometer/sources.json %{buildroot}%{_sysconfdir}/ceilometer/sources.json
install -p -D -m 640 etc/ceilometer/pipeline.yaml %{buildroot}%{_sysconfdir}/ceilometer/pipeline.yaml
#else
#raw
for i in etc/ceilometer/*; do
    if [ -f $i ] ; then
        install -p -D -m 640 $i  %{buildroot}%{_sysconfdir}/ceilometer
    fi
done
#end raw
mkdir -p %{buildroot}%{_sysconfdir}/ceilometer/rootwrap.d/
install -p -D -m 644 etc/ceilometer/rootwrap.d/* %{buildroot}%{_sysconfdir}/ceilometer/rootwrap.d/
#end if

%if ! (0%{?rhel} > 6)
# Install initscripts for services
install -p -D -m 755 %{SOURCE10} %{buildroot}%{_initrddir}/%{name}-api
install -p -D -m 755 %{SOURCE11} %{buildroot}%{_initrddir}/%{name}-collector
install -p -D -m 755 %{SOURCE12} %{buildroot}%{_initrddir}/%{name}-compute
install -p -D -m 755 %{SOURCE13} %{buildroot}%{_initrddir}/%{name}-central
install -p -D -m 755 %{SOURCE14} %{buildroot}%{_initrddir}/%{name}-alarm-notifier
install -p -D -m 755 %{SOURCE15} %{buildroot}%{_initrddir}/%{name}-alarm-evaluator
%else
install -p -D -m 755 %{SOURCE10} %{buildroot}%{_unitdir}/%{name}-api.service
install -p -D -m 755 %{SOURCE11} %{buildroot}%{_unitdir}/%{name}-collector.service
install -p -D -m 755 %{SOURCE12} %{buildroot}%{_unitdir}/%{name}-compute.service
install -p -D -m 755 %{SOURCE13} %{buildroot}%{_unitdir}/%{name}-central.service
install -p -D -m 755 %{SOURCE14} %{buildroot}%{_unitdir}/%{name}-alarm-notifier.service
install -p -D -m 755 %{SOURCE15} %{buildroot}%{_unitdir}/%{name}-alarm-evaluator.service
%endif
#if $newer_than_eq('2014.1')
%if ! (0%{?rhel} > 6)
install -p -D -m 755 %{SOURCE16} %{buildroot}%{_initrddir}/%{name}-notification
%else
install -p -D -m 755 %{SOURCE16} %{buildroot}%{_unitdir}/%{name}-notification.service
%endif
#end if
#if $newer_than_eq('2014.2')
%if ! (0%{?rhel} > 6)
install -p -D -m 755 %{SOURCE17} %{buildroot}%{_initrddir}/%{name}-ipmi
%else
install -p -D -m 755 %{SOURCE17} %{buildroot}%{_unitdir}/%{name}-ipmi.service
%endif
#end if
#if $newer_than_eq('2015.1')
%if ! (0%{?rhel} > 6)
install -p -D -m 755 %{SOURCE19} %{buildroot}%{_initrddir}/%{name}-polling
%else
install -p -D -m 755 %{SOURCE19} %{buildroot}%{_unitdir}/%{name}-polling.service
%endif
#end if
#Fix for bin path for central and compute
%if ! (0%{?rhel} > 6)
sed -i "s#/usr/bin/ceilometer-compute#/usr/bin/ceilometer-agent-compute#" %{buildroot}%{_initrddir}/%{name}-compute
sed -i "s#/usr/bin/ceilometer-central#/usr/bin/ceilometer-agent-central#" %{buildroot}%{_initrddir}/%{name}-central
%else
sed -i "s#/usr/bin/ceilometer-compute#/usr/bin/ceilometer-agent-compute#" %{buildroot}%{_unitdir}/%{name}-compute.service
sed -i "s#/usr/bin/ceilometer-central#/usr/bin/ceilometer-agent-central#" %{buildroot}%{_unitdir}/%{name}-central.service
%endif
#if $newer_than_eq('2014.1')
%if ! (0%{?rhel} > 6)
sed -i "s#/usr/bin/ceilometer-notification#/usr/bin/ceilometer-agent-notification#" %{buildroot}%{_initrddir}/%{name}-notification
%else
sed -i "s#/usr/bin/ceilometer-notification#/usr/bin/ceilometer-agent-notification#" %{buildroot}%{_unitdir}/%{name}-notification.service
%endif
#end if
# Install logrotate
install -p -D -m 644 %{SOURCE21} %{buildroot}%{_sysconfdir}/logrotate.d/%{name}

# Install pid directory
install -d -m 755 %{buildroot}%{_localstatedir}/run/ceilometer

# Remove unneeded in production stuff
rm -f %{buildroot}%{_bindir}/ceilometer-debug
rm -fr %{buildroot}%{python_sitelib}/tests/
rm -fr %{buildroot}%{python_sitelib}/run_tests.*
rm -f %{buildroot}/usr/share/doc/ceilometer/README*
rm -f %{buildroot}/%{python_sitelib}/ceilometer/api/v1/static/LICENSE.*

%pre common
getent group ceilometer >/dev/null || groupadd -r ceilometer --gid 166
if ! getent passwd ceilometer >/dev/null; then
  # Id reservation request: https://bugzilla.redhat.com/923891
  useradd -u 166 -r -g ceilometer -G ceilometer,nobody -d %{_sharedstatedir}/ceilometer -s /sbin/nologin -c "OpenStack ceilometer Daemons" ceilometer
fi
exit 0

%files common
%doc LICENSE
%dir %{_sysconfdir}/ceilometer
#if $older_than('2014.2')
%attr(-, root, ceilometer) %{_datadir}/ceilometer/ceilometer-dist.conf
%config(noreplace) %attr(-, root, ceilometer) %{_sysconfdir}/ceilometer/ceilometer.conf
%config(noreplace) %attr(-, root, ceilometer) %{_sysconfdir}/ceilometer/policy.json
%config(noreplace) %attr(-, root, ceilometer) %{_sysconfdir}/ceilometer/sources.json
%config(noreplace) %attr(-, root, ceilometer) %{_sysconfdir}/ceilometer/pipeline.yaml
#else
%config(noreplace) %attr(-, root, ceilometer) %{_sysconfdir}/ceilometer/*
#end if

%config(noreplace) %{_sysconfdir}/logrotate.d/%{name}
%dir %attr(0755, ceilometer, root) %{_localstatedir}/log/ceilometer
%dir %attr(0755, ceilometer, root) %{_localstatedir}/run/ceilometer

%{_bindir}/ceilometer-dbsync
%{_bindir}/ceilometer-expirer

%defattr(-, ceilometer, ceilometer, -)
%dir %{_sharedstatedir}/ceilometer
%dir %{_sharedstatedir}/ceilometer/tmp

%files -n python-ceilometer
%{python_sitelib}/ceilometer
%{python_sitelib}/ceilometer-%{os_version}*.egg-info

%if 0%{?with_doc}
%files doc
%doc doc/build/html
%endif

%files compute
%{_bindir}/ceilometer-agent-compute
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{name}-compute
%else
%{_unitdir}/%{name}-compute.service
%endif

%if 0%{?rhel} > 6
%post compute
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-compute.service
fi

%preun compute
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-compute.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-compute.service > /dev/null 2>&1 || :
fi

%postun compute
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-compute.service #>/dev/null 2>&1 || :
fi
%endif

%files collector
%{_bindir}/ceilometer-collector*
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{name}-collector
%else
%{_unitdir}/%{name}-collector.service
%endif

%if 0%{?rhel} > 6
%post collector
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-collector.service
fi

%preun collector
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-collector.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-collector.service > /dev/null 2>&1 || :
fi

%postun collector
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-collector.service #>/dev/null 2>&1 || :
fi
%endif

%files api
#if $older_than('2014.2')
%doc ceilometer/api/v1/static/LICENSE.*
#end if
%{_bindir}/ceilometer-api
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{name}-api
%else
%{_unitdir}/%{name}-api.service
%endif

%if 0%{?rhel} > 6
%post api
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-api.service
fi

%preun api
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-api.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-api.service > /dev/null 2>&1 || :
fi

%postun api
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-api.service #>/dev/null 2>&1 || :
fi
%endif

%files central
%{_bindir}/ceilometer-agent-central
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{name}-central
%else
%{_unitdir}/%{name}-central.service
%endif

%if 0%{?rhel} > 6
%post central
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-central.service
fi

%preun central
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-central.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-central.service > /dev/null 2>&1 || :
fi

%postun central
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-central.service #>/dev/null 2>&1 || :
fi
%endif

%files alarm
%{_bindir}/ceilometer-alarm-notifier
%{_bindir}/ceilometer-alarm-evaluator
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{name}-alarm-notifier
%{_initrddir}/%{name}-alarm-evaluator
%else
%{_unitdir}/%{name}-alarm-notifier.service
%{_unitdir}/%{name}-alarm-evaluator.service
%endif

%if 0%{?rhel} > 6
%post alarm
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-alarm-notifier.service
        /usr/bin/systemctl preset %{name}-alarm-evaluator.service
fi

%preun alarm
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-alarm-notifier.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-alarm-notifier.service > /dev/null 2>&1 || :
        /usr/bin/systemctl --no-reload disable %{name}-alarm-evaluator.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-alarm-evaluator.service > /dev/null 2>&1 || :
fi

%postun alarm
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-alarm-notifier.service #>/dev/null 2>&1 || :
        /usr/bin/systemctl try-restart %{name}-alarm-evaluator.service #>/dev/null 2>&1 || :
fi
%endif

#if $newer_than_eq('2014.1')
%files notification
%{_bindir}/ceilometer-agent-notification
%{_bindir}/ceilometer-send-sample
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{name}-notification
%else
%{_unitdir}/%{name}-notification.service
%endif

%if 0%{?rhel} > 6
%post notification
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-notification.service
fi

%preun notification
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-notification.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-notification.service > /dev/null 2>&1 || :
fi

%postun notification
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-notification.service #>/dev/null 2>&1 || :
fi
%endif
#end if

#if $newer_than_eq('2014.2')
%files ipmi
%config(noreplace) %attr(-, root, ceilometer) %{_sysconfdir}/ceilometer/rootwrap.d/ipmi.filters
%{_bindir}/ceilometer-agent-ipmi
%{_bindir}/ceilometer-rootwrap
%if 0%{?rhel} && 0%{?rhel} <= 6
%{_initrddir}/%{name}-ipmi
%else
%{_unitdir}/%{name}-ipmi.service
%endif


%if 0%{?rhel} > 6
%post ipmi
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-ipmi.service
fi

%preun ipmi
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-ipmi.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-ipmi.service > /dev/null 2>&1 || :
fi

%postun ipmi
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-ipmi.service #>/dev/null 2>&1 || :
fi
%endif
#end if

#if $newer_than_eq('2015.1')
%files polling
%{_bindir}/ceilometer-polling
%if 0%{?rhel} && 0%{?rhel} <= 6
%{_initrddir}/%{name}-polling
%else
%{_unitdir}/%{name}-polling.service
%endif

%if 0%{?rhel} > 6
%post polling
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-polling.service
fi

%preun polling
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-polling.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-polling.service > /dev/null 2>&1 || :
fi

%postun polling
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-polling.service #>/dev/null 2>&1 || :
fi
%endif
#end if

%changelog
