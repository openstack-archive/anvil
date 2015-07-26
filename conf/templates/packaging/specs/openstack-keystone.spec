#encoding UTF-8
# Based on spec by:
# * Andrey Brindeyev <abrindeyev@griddynamics.com>
# * Alessio Ababilov <aababilov@griddynamics.com>

%global python_name keystone
%global daemon_prefix openstack-keystone
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

Name:           openstack-keystone
Epoch:          $epoch
Version:        %{os_version}$version_suffix
Release:        $release%{?dist}
Url:            http://www.openstack.org
Summary:        Openstack Identity Service
License:        Apache 2.0
Vendor:         Openstack Foundation
Group:          Applications/System

Source0:        %{python_name}-%{os_version}.tar.gz
%if ! (0%{?rhel} > 6)
Source1:        openstack-keystone-all.init
%else
Source1:        openstack-keystone-all.service
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
Requires:         python-keystone = %{epoch}:%{version}-%{release}

%description
Keystone is a Python implementation of the OpenStack
(http://www.openstack.org) identity service API.

This package contains the Keystone daemon.


%if ! 0%{?no_tests}
%package -n python-%{python_name}-tests
Summary:          Tests for Keystone
Group:            Development/Libraries

Requires:         %{name} = %{epoch}:%{version}-%{release}
Requires:         python-%{python_name} = %{epoch}:%{version}-%{release}
# To test against modern client libraries
Requires:         git
Requires:         python-pbr

# Test requirements:
#for $i in $test_requires
Requires:         ${i}
#end for

%description -n python-%{python_name}-tests
Keystone is a Python implementation of the OpenStack
(http://www.openstack.org) identity service API.

This package contains unit and functional tests for Keystone, with
simple runner (%{python_name}-make-test-env).
%endif


%if 0%{?with_doc}

%package doc
Summary:          Documentation for %{name}
Group:            Documentation
Requires:         %{name} = %{epoch}:%{version}-%{release}

%description doc
Keystone is a Python implementation of the OpenStack
(http://www.openstack.org) identity service API.

This package contains documentation for Keystone.

%endif


%package -n      python-keystone
Summary:         Keystone Python libraries
Group:           Development/Languages/Python

#for $i in $requires
Requires:        ${i}
#end for

#for $i in $conflicts
Conflicts:       ${i}
#end for

%description -n  python-keystone
Keystone is a Python implementation of the OpenStack
(http://www.openstack.org) identity service API.

This package contains the Keystone Python library.

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
install -d -m 755 %{buildroot}%{_sysconfdir}/keystone
install -m 644 etc/* %{buildroot}%{_sysconfdir}/keystone

install -d -m 755 %{buildroot}%{_sharedstatedir}/keystone
install -d -m 755 %{buildroot}%{_localstatedir}/log/keystone
install -d -m 755 %{buildroot}%{_localstatedir}/run/keystone

%if ! (0%{?rhel} > 6)
install -p -D -m 755 %{SOURCE1} %{buildroot}%{_initrddir}/%{daemon_prefix}
%else
install -p -D -m 755 %{SOURCE1} %{buildroot}%{_unitdir}/%{daemon_prefix}.service
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
getent group keystone >/dev/null || groupadd -r keystone
getent passwd keystone >/dev/null || \
useradd -r -g keystone -d %{_sharedstatedir}/keystone -s /sbin/nologin \
-c "OpenStack Keystone Daemons" keystone
exit 0


%if 0%{?rhel} > 6
%post
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{daemon_prefix}.service
fi
%endif


%preun
if [ $1 = 0 ] ; then
%if ! (0%{?rhel} > 6)
    /sbin/service %{daemon_prefix} stop &>/dev/null
    /sbin/chkconfig --del %{daemon_prefix}
%else
    /usr/bin/systemctl --no-reload disable %{daemon_prefix}.service > /dev/null 2>&1 || :
    /usr/bin/systemctl stop %{daemon_prefix}.service > /dev/null 2>&1 || :
%endif
    exit 0
fi
%endif

%files
%defattr(-,root,root,-)
%doc README* LICENSE* HACKING* ChangeLog AUTHORS
%{_usr}/bin/*

%if ! 0%{?usr_only}
%configfile %{_sysconfdir}/keystone
%dir %attr(0755, keystone, nobody) %{_sharedstatedir}/keystone
%dir %attr(0755, keystone, nobody) %{_localstatedir}/log/keystone
%dir %attr(0755, keystone, nobody) %{_localstatedir}/run/keystone
%if ! (0%{?rhel} > 6)
%{_initrddir}/*
%else
%{_unitdir}/*
%endif
%endif

%if ! 0%{?no_tests}
%files -n python-%{python_name}-tests
%{tests_data_dir}
%{_bindir}/%{python_name}-make-test-env
%endif

%if 0%{?with_doc}
%files doc
%defattr(-,root,root,-)
%doc doc
%endif

%files -n python-keystone
%defattr(-,root,root,-)
%doc LICENSE
%{python_sitelib}/*

%changelog
#end raw
