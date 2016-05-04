#encoding UTF-8
# Based on spec by:
# * Andrey Brindeyev <abrindeyev@griddynamics.com>
# * Alessio Ababilov <aababilov@griddynamics.com>

%global python_name trove
%global daemon_prefix openstack-trove
%global os_version $version
%global no_tests $no_tests
%global tests_data_dir %{_datarootdir}/%{python_name}-tests

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 5)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

%if ! 0%{?overwrite_configs}
%global configfile %config(noreplace)
%else
%global configfile %verify(mode)
%endif

Name:           openstack-trove
Epoch:          $epoch
Version:        %{os_version}$version_suffix
Release:        $release%{?dist}
Url:            http://www.openstack.org
Summary:        Database as a Service
License:        Apache 2.0
Vendor:         Openstack Foundation
Group:          Applications/System

Source0:        %{python_name}-%{os_version}.tar.gz

%if ! (0%{?rhel} > 6)
Source1:        openstack-trove-server.init
Source2:        openstack-trove-api.init
%else
Source1:        openstack-trove-server.service
Source2:        openstack-trove-api.service
%endif

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}

BuildArch:        noarch
BuildRequires:    python-devel
BuildRequires:    python-setuptools
BuildRequires:    python-pbr

%if ! 0%{?usr_only}
Requires(post):   chkconfig
Requires(postun): initscripts
Requires(preun):  chkconfig
Requires(pre):    shadow-utils
%endif
Requires:         python-trove = %{epoch}:%{version}-%{release}

%description
Trove is Database as a Service for Openstack. It's designed to run
entirely on OpenStack, with the goal of allowing users to quickly and
easily utilize the features of a relational database without the burden
of handling complex administrative tasks.

This package contains the Trove daemon.


%if 0%{?with_doc}

%package doc
Summary:          Documentation for %{name}
Group:            Documentation
Requires:         %{name} = %{epoch}:%{version}-%{release}

%description doc
Trove is Database as a Service for Openstack. It's designed to run
entirely on OpenStack, with the goal of allowing users to quickly and
easily utilize the features of a relational database without the burden
of handling complex administrative tasks.

This package contains documentation for Trove.

%endif


%package -n      python-trove
Summary:         Trove Python libraries
Group:           Development/Languages/Python

#for $i in $requires
Requires:        ${i}
#end for

#for $i in $conflicts
Conflicts:       ${i}
#end for

%description -n  python-trove
Trove is Database as a Service for Openstack. It's designed to run
entirely on OpenStack, with the goal of allowing users to quickly and
easily utilize the features of a relational database without the burden
of handling complex administrative tasks.

This package contains the Trove Python library.


%if ! 0%{?no_tests}
%package -n python-%{python_name}-tests
Summary:          Tests for Trove
Group:            Development/Libraries

Requires:         %{name} = %{epoch}:%{version}-%{release}
Requires:         python-%{python_name} = %{epoch}:%{version}-%{release}

# Test requirements:
#for $i in $test_requires
Requires:         ${i}
#end for

%description -n python-%{python_name}-tests
Trove is Database as a Service for OpenStack.

This package contains unit and functional tests for Trove, with
simple runner (%{python_name}-make-test-env).
%endif


%prep
%setup -q -n %{python_name}-%{os_version}
#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for

%build

export PBR_VERSION=$version
%{__python} setup.py build


%install

export PBR_VERSION=$version
%__rm -rf %{buildroot}

%if 0%{?with_doc}

#raw
export PYTHONPATH="$PWD:$PYTHONPATH"
#end raw

pushd doc
sphinx-build -b html source build/html
popd

# Fix hidden-file-or-dir warnings
rm -fr doc/build/html/.doctrees doc/build/html/.buildinfo
%endif

%{__python} setup.py install --prefix=%{_prefix} --root=%{buildroot}

%if ! 0%{?usr_only}

# Install config files
install -d -m 755 %{buildroot}%{_sysconfdir}/trove
install -p -D -m 640 etc/trove/api-paste.ini %{buildroot}%{_sysconfdir}/trove/
install -p -D -m 640 etc/trove/trove.conf.sample %{buildroot}%{_sysconfdir}/trove/
install -p -D -m 640 etc/trove/trove-guestagent.conf.sample %{buildroot}%{_sysconfdir}/trove/
install -p -D -m 640 etc/trove/trove-taskmanager.conf.sample %{buildroot}%{_sysconfdir}/trove/

install -d -m 755 %{buildroot}%{_sharedstatedir}/trove
install -d -m 755 %{buildroot}%{_localstatedir}/log/trove
install -d -m 755 %{buildroot}%{_localstatedir}/run/trove

# Initscripts
%if ! (0%{?rhel} > 6)
install -p -D -m 755 %{SOURCE1} %{buildroot}%{_initrddir}/%{daemon_prefix}-api
install -p -D -m 755 %{SOURCE2} %{buildroot}%{_initrddir}/%{daemon_prefix}-server
%else
install -p -D -m 755 %{SOURCE1} %{buildroot}%{_unitdir}/%{daemon_prefix}-api.service
install -p -D -m 755 %{SOURCE2} %{buildroot}%{_unitdir}/%{daemon_prefix}-server.service
%endif
%endif

%__rm -rf %{buildroot}%{py_sitelib}/{doc,tools}

%if ! 0%{?no_tests}
#include $part_fn("install_tests.sh")
#raw
%endif


%clean
%__rm -rf %{buildroot}


%if ! 0%{?usr_only}
%pre
getent group trove >/dev/null || groupadd -r trove
getent passwd trove >/dev/null || \
useradd -r -g trove -d %{_sharedstatedir}/trove -s /sbin/nologin \
-c "OpenStack Trove Daemons" trove
exit 0


%if 0%{?rhel} > 6
%post
if [ \$1 -eq 1 ] ; then
    # Initial installation
    /usr/bin/systemctl preset %{daemon_prefix}-api.service
    /usr/bin/systemctl preset %{daemon_prefix}-server.service
fi
%endif


%preun
if [ $1 = 0 ] ; then
%if ! (0%{?rhel} > 6)
    /sbin/service %{daemon_prefix}-api stop &>/dev/null
    /sbin/chkconfig --del %{daemon_prefix}-api
    /sbin/service %{daemon_prefix}-server stop &>/dev/null
    /sbin/chkconfig --del %{daemon_prefix}-server
%else
    /usr/bin/systemctl --no-reload disable %{daemon_prefix}-api.service > /dev/null 2>&1 || :
    /usr/bin/systemctl stop %{daemon_prefix}-api.service > /dev/null 2>&1 || :
    /usr/bin/systemctl --no-reload disable %{daemon_prefix}-server.service > /dev/null 2>&1 || :
    /usr/bin/systemctl stop %{daemon_prefix}-server.service > /dev/null 2>&1 || :
%endif
    exit 0
fi

%postun
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
%if ! (0%{?rhel} > 6)
    /sbin/service %{daemon_prefix}-api condrestart &>/dev/null
    /sbin/service %{daemon_prefix}-server condrestart &>/dev/null
%else
    /usr/bin/systemctl try-restart %{daemon_prefix}-api.service #>/dev/null 2>&1 || :
    /usr/bin/systemctl try-restart %{daemon_prefix}-server.service #>/dev/null 2>&1 || :
%endif
    exit 0
fi
%endif


%files
%defattr(-,root,root,-)
%doc README* LICENSE* ChangeLog AUTHORS
%{_usr}/bin/*

%if ! 0%{?usr_only}
%configfile %{_sysconfdir}/trove
%dir %attr(0755, trove, nobody) %{_sharedstatedir}/trove
%dir %attr(0755, trove, nobody) %{_localstatedir}/log/trove
%dir %attr(0755, trove, nobody) %{_localstatedir}/run/trove
%if ! (0%{?rhel} > 6)
%{_initrddir}/*
%else
%{_unitdir}/*
%endif
%endif

%if 0%{?with_doc}
%files doc
%defattr(-,root,root,-)
%doc doc
%endif

%files -n python-trove
%defattr(-,root,root,-)
%doc LICENSE
%{python_sitelib}/*

%if ! 0%{?no_tests}
%files -n python-%{python_name}-tests
%{tests_data_dir}
%{_bindir}/%{python_name}-make-test-env
%endif

%changelog
#endraw
