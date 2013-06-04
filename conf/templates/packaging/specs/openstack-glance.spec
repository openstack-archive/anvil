%global python_name glance
%global daemon_prefix openstack-glance

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

Name:             openstack-glance
Epoch:            $epoch
Version:          $version
Release:          1%{?dist}
Summary:          OpenStack Image Registry and Delivery Service

Group:            Development/Languages
License:          ASL 2.0
Vendor:           OpenStack Foundation
URL:              http://glance.openstack.org
Source0:          %{python_name}-%{version}.tar.gz
Source1:          openstack-glance-api.init
Source2:          openstack-glance-registry.init
Source3:          openstack-glance-scrubber.init
Source4:          openstack-glance.logrotate

BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}

BuildArch:        noarch
BuildRequires:    python-devel
BuildRequires:    python-setuptools

Requires(post):   chkconfig
Requires(postun): initscripts
Requires(preun):  chkconfig
Requires(pre):    shadow-utils
Requires:         python-glance = %{epoch}:%{version}-%{release}

%description
OpenStack Image Service (code-named Glance) provides discovery, registration,
and delivery services for virtual disk images. The Image Service API server
provides a standard REST interface for querying information about virtual disk
images stored in a variety of back-end stores, including OpenStack Object
Storage. Clients can register new virtual disk images with the Image Service,
query for information on publicly available disk images, and use the Image
Service client library for streaming virtual disk images.

This package contains the API and registry servers.

%package -n       python-glance
Summary:          Glance Python libraries
Group:            Applications/System

#for $i in $requires
Requires:	  ${i}
#end for

#raw
%description -n   python-glance
OpenStack Image Service (code-named Glance) provides discovery, registration,
and delivery services for virtual disk images.

This package contains the glance Python library.

%if 0%{?with_doc}
%package doc
Summary:          Documentation for OpenStack Glance
Group:            Documentation

BuildRequires:    python-sphinx
BuildRequires:    graphviz

# Required to build module documents
BuildRequires:    python-boto
BuildRequires:    python-daemon
BuildRequires:    python-eventlet

%description      doc
OpenStack Image Service (code-named Glance) provides discovery, registration,
and delivery services for virtual disk images.

This package contains documentation files for glance.

%endif

%prep
%setup -q -n %{python_name}-%{version}
sed '/pysendfile/d' tools/pip-requires


%build
%{__python} setup.py build

%install
rm -rf %{buildroot}
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

# Delete tests
rm -fr %{buildroot}%{python_sitelib}/tests

%if 0%{?with_doc}
export PYTHONPATH="$PWD:$PYTHONPATH"
pushd doc
sphinx-build -b html source build/html
popd

# Fix hidden-file-or-dir warnings
rm -fr doc/build/html/.doctrees doc/build/html/.buildinfo
%endif

# Setup directories
install -d -m 755 %{buildroot}%{_sharedstatedir}/glance/images

# Config file
install -d -m 755 %{buildroot}%{_sysconfdir}/glance
for i in etc/*; do
    install -p -D -m 644 $i  %{buildroot}%{_sysconfdir}/glance/
done

# Initscripts
install -p -D -m 755 %{SOURCE1} %{buildroot}%{_initrddir}/%{daemon_prefix}-api
install -p -D -m 755 %{SOURCE2} %{buildroot}%{_initrddir}/%{daemon_prefix}-registry
install -p -D -m 755 %{SOURCE3} %{buildroot}%{_initrddir}/%{daemon_prefix}-scrubber

# Logrotate config
install -p -D -m 644 %{SOURCE4} %{buildroot}%{_sysconfdir}/logrotate.d/openstack-glance

# Install pid directory
install -d -m 755 %{buildroot}%{_localstatedir}/run/glance

# Install log directory
install -d -m 755 %{buildroot}%{_localstatedir}/log/glance


%clean
rm -rf %{buildroot}


%pre
getent group glance >/dev/null || groupadd -r glance
getent passwd glance >/dev/null || \
useradd -r -g glance -d %{_sharedstatedir}/glance -s /sbin/nologin \
-c "OpenStack Glance Daemons" glance
exit 0


%preun
if [ $1 = 0 ] ; then
    for svc in api registry scrubber; do
        /sbin/service %{daemon_prefix}-${svc} stop &>/dev/null
        /sbin/chkconfig --del %{daemon_prefix}-${svc}
    done
    exit 0
fi


%postun
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    for svc in api registry scrubber; do
        /sbin/service %{daemon_prefix}-${svc} condrestart &>/dev/null
    done
    exit 0
fi


%files
%defattr(-,root,root,-)
%doc README* LICENSE* HACKING* ChangeLog
%{_bindir}/*
%{_initrddir}/*
%dir %{_sysconfdir}/glance
%config(noreplace) %attr(-, root, glance) %{_sysconfdir}/glance/*
%config(noreplace) %attr(-, root, glance) %{_sysconfdir}/logrotate.d/openstack-glance
%dir %attr(0755, glance, nobody) %{_sharedstatedir}/glance
%dir %attr(0755, glance, nobody) %{_localstatedir}/log/glance
%dir %attr(0755, glance, nobody) %{_localstatedir}/run/glance


%files -n python-glance
%{python_sitelib}/*

%if 0%{?with_doc}
%files doc
%defattr(-,root,root,-)
%doc doc/build/html
%endif

%changelog
#end raw
