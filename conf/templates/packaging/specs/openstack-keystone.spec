#encoding UTF-8
# Based on spec by:
# * Andrey Brindeyev <abrindeyev@griddynamics.com>
# * Alessio Ababilov <aababilov@griddynamics.com>

%global python_name keystone
%global daemon_prefix openstack-keystone
%global os_version $version

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 5)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
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
Source1:        openstack-keystone-all.init

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

Requires:         python-nose
Requires:         python-openstack-nose-plugin
Requires:         python-nose-exclude

#for $i in $test_requires
Requires:         ${i}
#end for

%description -n python-%{python_name}-tests
Keystone is a Python implementation of the OpenStack
(http://www.openstack.org) identity service API.

This package contains unit and functional tests for Keystone, with
simple runner (%{python_name}-run-unit-tests).
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

%description -n  python-keystone
Keystone is a Python implementation of the OpenStack
(http://www.openstack.org) identity service API.

This package contains the Keystone Python library.

%prep
%setup -q -n %{python_name}-%{os_version}
#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for
#raw

%build
python setup.py build


%install
%__rm -rf %{buildroot}

%if 0%{?with_doc}
export PYTHONPATH="$PWD:$PYTHONPATH"

pushd doc
sphinx-build -b html source build/html
popd

# Fix hidden-file-or-dir warnings
rm -fr doc/build/html/.doctrees doc/build/html/.buildinfo
%endif

python setup.py install --prefix=%{_prefix} --root=%{buildroot}


%if ! 0%{?usr_only}
install -d -m 755 %{buildroot}%{_sysconfdir}/keystone
install -m 644 etc/* %{buildroot}%{_sysconfdir}/keystone

install -d -m 755 %{buildroot}%{_sharedstatedir}/keystone
install -d -m 755 %{buildroot}%{_localstatedir}/log/keystone
install -d -m 755 %{buildroot}%{_localstatedir}/run/keystone

install -p -D -m 755 %{SOURCE1} %{buildroot}%{_initrddir}/%{daemon_prefix}-all
%endif

%__rm -rf %{buildroot}%{py_sitelib}/{doc,tools}

%if ! 0%{?no_tests}

# Copy tests and test assets
install -d -m 755 %{buildroot}%{python_sitelib}/%{python_name}/tests/assets/
cp -a tests %{buildroot}%{python_sitelib}/%{python_name}/
cp -a etc examples %{buildroot}%{python_sitelib}/%{python_name}/tests/assets/

chown -R root:root %{buildroot}%{python_sitelib}/%{python_name}/tests
find %{buildroot}%{python_sitelib}/%{python_name}/tests -type d | xargs chmod 0755
find %{buildroot}%{python_sitelib}/%{python_name}/tests -type f | xargs chmod 0644


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


%clean
%__rm -rf %{buildroot}


%if ! 0%{?usr_only}
%pre
getent group keystone >/dev/null || groupadd -r keystone
getent passwd keystone >/dev/null || \
useradd -r -g keystone -d %{_sharedstatedir}/keystone -s /sbin/nologin \
-c "OpenStack Keystone Daemons" keystone
exit 0


%preun
if [ $1 = 0 ] ; then
    /sbin/service %{daemon_prefix}-all stop &>/dev/null
    /sbin/chkconfig --del %{daemon_prefix}-all
    exit 0
fi

%postun
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    /sbin/service %{daemon_prefix}-all condrestart &>/dev/null
    exit 0
fi
%endif


%files
%defattr(-,root,root,-)
%doc README* LICENSE* HACKING* ChangeLog AUTHORS
%{_usr}/bin/*

%if ! 0%{?usr_only}
%config(noreplace) %{_sysconfdir}/keystone
%dir %attr(0755, keystone, nobody) %{_sharedstatedir}/keystone
%dir %attr(0755, keystone, nobody) %{_localstatedir}/log/keystone
%dir %attr(0755, keystone, nobody) %{_localstatedir}/run/keystone
%{_initrddir}/*
%endif

%if ! 0%{?no_tests}
%files -n python-%{python_name}-tests
%{python_sitelib}/%{python_name}/test.py*
%{python_sitelib}/%{python_name}/tests
# TODO(imelnikov): this tests don't work:
%exclude %{python_sitelib}/%{python_name}/tests/test_keystoneclient*
%{_bindir}/%{python_name}-run-unit-tests
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
%exclude %{python_sitelib}/%{python_name}/tests
%exclude %{python_sitelib}/%{python_name}/test.py*

%changelog
#endraw
