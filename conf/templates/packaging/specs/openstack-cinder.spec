#encoding UTF-8
# Based on spec by:
# * Eric Harney <eharney@redhat.com>
# * Martin Magr <mmagr@redhat.com>
# * Pádraig Brady <P@draigBrady.com>

%global python_name cinder
%global daemon_prefix openstack-cinder
%global os_version $version

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

Name:	          openstack-cinder
Version:          %{os_version}$version_suffix
Release:          $release%{?dist}
Epoch:            $epoch
Summary:          OpenStack Volume service

Group:            Applications/System
License:          ASL 2.0
URL:              http://www.openstack.org/software/openstack-storage/
Source0:          %{python_name}-%{os_version}.tar.gz
Source1:          cinder-sudoers
Source2:          cinder.logrotate
Source3:          cinder-tgt.conf

Source10:         openstack-cinder-api.init
Source11:         openstack-cinder-scheduler.init
Source12:         openstack-cinder-volume.init
Source13:         openstack-cinder-all.init

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

BuildArch:        noarch
BuildRequires:    python-setuptools

Requires:         python-cinder = %{epoch}:%{version}-%{release}

# as convenience
Requires:         python-cinderclient

%if ! 0%{?usr_only}
Requires(post):   chkconfig
Requires(preun):  chkconfig
Requires(postun): chkconfig
Requires(pre):    shadow-utils
%endif

Requires:         lvm2
Requires:         scsi-target-utils

%description
OpenStack Volume (codename Cinder) provides services to manage and
access block storage volumes for use by Virtual Machine instances.


%package -n       python-cinder
Summary:          OpenStack Volume Python libraries
Group:            Applications/System

Requires:	sudo
#for $i in $requires
Requires:        ${i}
#end for


%description -n   python-cinder
OpenStack Volume (codename Cinder) provides services to manage and
access block storage volumes for use by Virtual Machine instances.

This package contains the cinder Python library.

%if 0%{?with_doc}
%package doc
Summary:          Documentation for OpenStack Volume
Group:            Documentation

Requires:         %{name} = %{epoch}:%{version}-%{release}

BuildRequires:    graphviz
BuildRequires:    python-sphinx

# Required to build module documents
BuildRequires:    python-eventlet
BuildRequires:    python-routes
BuildRequires:    python-sqlalchemy
BuildRequires:    python-webob
# while not strictly required, quiets the build down when building docs.
BuildRequires:    python-migrate, python-iso8601

%description      doc
OpenStack Volume (codename Cinder) provides services to manage and
access block storage volumes for use by Virtual Machine instances.

This package contains documentation files for cinder.
%endif

%prep
%setup -q -n cinder-%{os_version}
#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for
#raw

# Ensure we don't access the net when building docs
sed -i "/'sphinx.ext.intersphinx',/d" doc/source/conf.py
# Remove deprecated assert_unicode sqlalchemy attribute
sed -i "/assert_unicode=None/d" cinder/db/sqlalchemy/migrate_repo/versions/*py

find . \( -name .gitignore -o -name .placeholder \) -delete

find cinder -name \*.py -exec sed -i '/\/usr\/bin\/env python/{d;q}' {} +

# TODO: Have the following handle multi line entries
sed -i '/setup_requires/d; /install_requires/d; /dependency_links/d' setup.py

%build

%{__python} setup.py build

%install
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

# docs generation requires everything to be installed first
export PYTHONPATH="$PWD:$PYTHONPATH"

%if 0%{?with_doc}
pushd doc

SPHINX_DEBUG=1 sphinx-build -b html source build/html
# Fix hidden-file-or-dir warnings
rm -fr build/html/.doctrees build/html/.buildinfo

# Create dir link to avoid a sphinx-build exception
mkdir -p build/man/.doctrees/
ln -s .  build/man/.doctrees/man
SPHINX_DEBUG=1 sphinx-build -b man -c source source/man build/man
mkdir -p %{buildroot}%{_mandir}/man1
install -p -D -m 644 build/man/*.1 %{buildroot}%{_mandir}/man1/

popd
%endif

%if ! 0%{?usr_only}
# Setup directories
install -d -m 755 %{buildroot}%{_sharedstatedir}/cinder
install -d -m 755 %{buildroot}%{_sharedstatedir}/cinder/tmp
install -d -m 755 %{buildroot}%{_localstatedir}/log/cinder

# Install config files
install -d -m 755 %{buildroot}%{_sysconfdir}/cinder
install -d -m 755 %{buildroot}%{_sysconfdir}/cinder/volumes
install -p -D -m 644 %{SOURCE3} %{buildroot}%{_sysconfdir}/tgt/conf.d/cinder.conf
install -p -D -m 640 etc/cinder/cinder.conf.sample %{buildroot}%{_sysconfdir}/cinder/
install -p -D -m 640 etc/cinder/rootwrap.conf %{buildroot}%{_sysconfdir}/cinder/
install -p -D -m 640 etc/cinder/api-paste.ini %{buildroot}%{_sysconfdir}/cinder/
install -p -D -m 640 etc/cinder/policy.json %{buildroot}%{_sysconfdir}/cinder/

# Install initscripts for services
install -p -D -m 755 %{SOURCE10} %{buildroot}%{_initrddir}/%{daemon_prefix}-api
install -p -D -m 755 %{SOURCE11} %{buildroot}%{_initrddir}/%{daemon_prefix}-scheduler
install -p -D -m 755 %{SOURCE12} %{buildroot}%{_initrddir}/%{daemon_prefix}-volume
install -p -D -m 755 %{SOURCE13} %{buildroot}%{_initrddir}/%{daemon_prefix}-all

# Install sudoers
install -p -D -m 440 %{SOURCE1} %{buildroot}%{_sysconfdir}/sudoers.d/cinder

# Install logrotate
install -p -D -m 644 %{SOURCE2} %{buildroot}%{_sysconfdir}/logrotate.d/openstack-cinder

# Install pid directory
install -d -m 755 %{buildroot}%{_localstatedir}/run/cinder
%endif

# Install rootwrap files in /usr/share/cinder/rootwrap
mkdir -p %{buildroot}%{_datarootdir}/cinder/rootwrap/
install -p -D -m 644 etc/cinder/rootwrap.d/* %{buildroot}%{_datarootdir}/cinder/rootwrap/

# Remove unneeded in production stuff
rm -f %{buildroot}%{_bindir}/cinder-debug
rm -fr %{buildroot}%{python_sitelib}/cinder/tests/
rm -fr %{buildroot}%{python_sitelib}/run_tests.*
rm -f %{buildroot}/usr/share/doc/cinder/README*


%if ! 0%{?usr_only}
%pre
getent group cinder >/dev/null || groupadd -r cinder
getent passwd cinder >/dev/null || \
useradd -r -g cinder -d %{_sharedstatedir}/cinder -s /sbin/nologin \
-c "OpenStack Cinder Daemons" cinder
exit 0


%preun
if [ $1 -eq 0 ] ; then
    for svc in all volume api scheduler; do
        /sbin/chkconfig --del %{daemon_prefix}-${svc} &>/dev/null
        /sbin/service %{daemon_prefix}-${svc} stop &>/dev/null
    done
    exit 0
fi

%postun
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    for svc in all volume api scheduler; do
        /sbin/service %{daemon_prefix}-${svc} condrestart &>/dev/null
    done
    exit 0
fi
%endif


%files
%doc README* LICENSE* HACKING* ChangeLog AUTHORS
%{_bindir}/cinder-*
%{_datarootdir}/cinder
%if 0%{?with_doc}
%{_mandir}/man1/*
%endif

%if ! 0%{?usr_only}
%{_initrddir}/*

%dir %{_sysconfdir}/cinder
%config(noreplace) %attr(-, root, cinder) %{_sysconfdir}/cinder/cinder.conf.sample
%config(noreplace) %attr(-, root, cinder) %{_sysconfdir}/cinder/api-paste.ini
%config(noreplace) %attr(-, root, cinder) %{_sysconfdir}/cinder/rootwrap.conf
%config(noreplace) %attr(-, root, cinder) %{_sysconfdir}/cinder/policy.json
%config(noreplace) %{_sysconfdir}/logrotate.d/openstack-cinder
%config(noreplace) %{_sysconfdir}/sudoers.d/cinder
%config(noreplace) %{_sysconfdir}/tgt/conf.d/cinder.conf

%dir %attr(0755, cinder, root) %{_localstatedir}/log/cinder
%dir %attr(0755, cinder, root) %{_localstatedir}/run/cinder
%dir %attr(0755, cinder, root) %{_sysconfdir}/cinder/volumes

%defattr(-, cinder, cinder, -)
%dir %{_sharedstatedir}/cinder
%dir %{_sharedstatedir}/cinder/tmp
%endif

%files -n python-cinder
%doc LICENSE
%{python_sitelib}/cinder
%{python_sitelib}/cinder-%{os_version}*.egg-info


%if 0%{?with_doc}
%files doc
%doc doc/build/html
%endif

%changelog
#end raw
