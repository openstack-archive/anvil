#encoding UTF-8
%global python_name django_openstack_auth
%global os_version $version
%global no_tests $no_tests
%global tests_data_dir %{_datarootdir}/%{python_name}-tests

Name:       python-django-openstack-auth
Version:    %{os_version}$version_suffix
Release:    $release%{?dist}
Epoch:      ${epoch}
Summary:    Django authentication backend for use with OpenStack Identity

Group:      Development/Libraries
License:    ASL 2.0
URL:        http://www..openstack.org/
BuildArch:  noarch
Vendor:     Openstack Foundation
Source0:    django-openstack-auth-%{os_version}.tar.gz

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

# additional provides to be consistent with other django packages
Provides:   django-openstack-auth = %{epoch}:%{version}-%{release}

%if 0%{?rhel}==6
BuildRequires: Django14
%else
BuildRequires: python-django
%endif

#for $i in $requires
Requires:         ${i}
#end for

Conflicts:    django-openstack-auth

%description
Django OpenStack Auth is a pluggable Django authentication backend that
works with Django's ``contrib.auth`` framework to authenticate a user against
OpenStack's Keystone Identity API.

%if ! 0%{?no_tests}
%package -n       python-%{python_name}-tests
Summary:          Tests for Horizon authentication backend
Group:            Development/Libraries

Requires:         %{name} = %{epoch}:%{version}-%{release}

# Test requirements:
#for $i in $test_requires
Requires:         ${i}
#end for

#for $i in $conflicts
Conflicts:       ${i}
#end for

%description -n python-%{python_name}-tests
Django OpenStack Auth is a pluggable Django authentication backend that
works with Django's ``contrib.auth`` framework to authenticate a user against
OpenStack's Keystone Identity API.

This package contains unit and functional tests for Django OpenStack Auth, with
simple runner (%{python_name}-make-test-env).
%endif

%prep
%setup -q -n django-openstack-auth-%{os_version}
#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for

#raw
%build
%{__python} setup.py build

%install
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

%if ! 0%{?no_tests}
install -d -m 755 %{buildroot}%{_bindir}
#end raw
#include $part_fn("install_tests.sh")
#raw
%endif

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root)
%doc README* LICENSE*

%if ! 0%{?no_tests}
%files -n python-%{python_name}-tests
%{tests_data_dir}
%{_bindir}/%{python_name}-make-test-env
%endif

%files -n python-django-openstack-auth
%defattr(-,root,root,-)
%doc LICENSE
%{python_sitelib}/*


%changelog
#end raw
