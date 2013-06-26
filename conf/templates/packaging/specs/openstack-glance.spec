#encoding UTF-8
# Based on spec by:
# * Andrey Brindeyev <abrindeyev@griddynamics.com>
# * Alessio Ababilov <aababilov@griddynamics.com>

%global python_name glance
%global daemon_prefix openstack-glance
%global os_version $version

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

Name:             openstack-glance
Epoch:            $epoch
Version:          %{os_version}$version_suffix
Release:          $release%{?dist}
Summary:          OpenStack Image Registry and Delivery Service

Group:            Development/Languages
License:          ASL 2.0
Vendor:           OpenStack Foundation
URL:              http://glance.openstack.org
Source0:          %{python_name}-%{os_version}.tar.gz
Source1:          openstack-glance-api.init
Source2:          openstack-glance-registry.init
Source3:          openstack-glance-scrubber.init
Source4:          openstack-glance.logrotate

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}

BuildArch:        noarch
BuildRequires:    python-devel
BuildRequires:    python-setuptools

%if ! 0%{?usr_only}
Requires(post):   chkconfig
Requires(postun): initscripts
Requires(preun):  chkconfig
Requires(pre):    shadow-utils
%endif

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

%description -n   python-glance
OpenStack Image Service (code-named Glance) provides discovery, registration,
and delivery services for virtual disk images.

This package contains the glance Python library.


%if ! 0%{?no_tests}
%package -n python-glance-tests
Summary:          Tests for Glance
Group:            Development/Libraries

Requires:         openstack-glance = %{epoch}:%{version}-%{release}
Requires:         python-glance = %{epoch}:%{version}-%{release}
Requires:         python-nose
Requires:         python-openstack-nose-plugin
Requires:         python-nose-exclude

#for $i in $test_requires
Requires:         ${i}
#end for

%description -n python-glance-tests
OpenStack Image Service (code-named Glance) provides discovery, registration,
and delivery services for virtual disk images.

This package contains the Glance unit and functional tests, with simple
runner (glance-run-unit-tests).
%endif

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
%setup -q -n %{python_name}-%{os_version}
#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for

#raw

# make tests run real installed binaries
find glance/tests -name '*.py' | while read filename; do
    sed -i \
        -e "s,\./bin/glance,%{_bindir}/glance,g" \
        -e "s,\('\|\"\)bin/glance,\1%{_bindir}/glance,g" \
        "$filename"
done

%build
%{__python} setup.py build

%install
rm -rf %{buildroot}
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

%if 0%{?with_doc}
export PYTHONPATH="$PWD:$PYTHONPATH"
pushd doc
sphinx-build -b html source build/html
popd

# Fix hidden-file-or-dir warnings
rm -fr doc/build/html/.doctrees doc/build/html/.buildinfo
%endif

%if ! 0%{?usr_only}
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
%endif

%if ! 0%{?no_tests}
# Make simple test runner
cat > %{buildroot}%{_bindir}/glance-run-unit-tests << EOF
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
    glance/tests "\$@"

EOF
chmod 0755 %{buildroot}%{_bindir}/glance-run-unit-tests
%endif

%clean
rm -rf %{buildroot}


%if ! 0%{?usr_only}
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
%endif


%files
%defattr(-,root,root,-)
%doc README* LICENSE* HACKING* ChangeLog AUTHORS
%{_bindir}/*
%exclude %{_bindir}/glance-run-unit-tests

%if ! 0%{?usr_only}
%{_initrddir}/*
%dir %{_sysconfdir}/glance
%config(noreplace) %attr(-, root, glance) %{_sysconfdir}/glance/*
%config(noreplace) %attr(-, root, glance) %{_sysconfdir}/logrotate.d/openstack-glance
%dir %attr(0755, glance, nobody) %{_sharedstatedir}/glance
%dir %attr(0755, glance, nobody) %{_localstatedir}/log/glance
%dir %attr(0755, glance, nobody) %{_localstatedir}/run/glance
%endif

%files -n python-glance
%{python_sitelib}/*
%exclude %{python_sitelib}/glance/tests

%if ! 0%{?no_tests}
%files -n python-glance-tests
%{python_sitelib}/glance/tests
%{_bindir}/glance-run-unit-tests
%endif

%if 0%{?with_doc}
%files doc
%defattr(-,root,root,-)
%doc doc/build/html
%endif

%changelog
#end raw
