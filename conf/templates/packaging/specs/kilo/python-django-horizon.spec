#encoding UTF-8
# Based on spec by:
# * Matthias Runge <mrunge@redhat.com>
# * Pádraig Brady <P@draigBrady.com>
# * Alan Pevec <apevec@redhat.com>
# * Cole Robinson <crobinso@redhat.com>

%global python_name horizon
%global os_version $version
%global no_tests $no_tests
%global tests_data_dir %{_datarootdir}/%{python_name}-tests

%global with_compression 1

Name:       python-django-horizon
Version:    %{os_version}$version_suffix
Release:    $release%{?dist}
Epoch:      ${epoch}
Summary:    Django application for talking to Openstack

Group:      Development/Libraries
# Code in horizon/horizon/utils taken from django which is BSD
License:    ASL 2.0 and BSD
URL:        http://horizon.openstack.org/
BuildArch:  noarch
Source0:    horizon-%{os_version}.tar.gz
Source1:    openstack-dashboard.conf
Source2:    openstack-dashboard-httpd-2.4.conf

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

# additional provides to be consistent with other django packages
Provides:   django-horizon = %{epoch}:%{version}-%{release}

%if 0%{?rhel}==6
BuildRequires: Django14
%else
BuildRequires: python-django
%endif

BuildRequires: python-devel
BuildRequires: python-setuptools

#if $newer_than_eq('2014.1')
BuildRequires: python-oslo-config
BuildRequires: python-django-compressor
BuildRequires: python-eventlet
BuildRequires: python-iso8601
%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
BuildRequires: python-requests
BuildRequires: python-netaddr
%endif
#end if
#if $newer_than_eq('2014.2')
BuildRequires: python-xstatic
BuildRequires: python-xstatic-angular
BuildRequires: python-xstatic-angular-cookies
BuildRequires: python-xstatic-angular-mock
BuildRequires: python-xstatic-bootstrap-datepicker
BuildRequires: python-xstatic-bootstrap-scss
BuildRequires: python-xstatic-d3
BuildRequires: python-xstatic-hogan
BuildRequires: python-xstatic-font-awesome
BuildRequires: python-xstatic-jasmine
BuildRequires: python-xstatic-jquery
BuildRequires: python-xstatic-jquery-migrate
BuildRequires: python-xstatic-jquery-quicksearch
BuildRequires: python-xstatic-jquery-tablesorter
BuildRequires: python-xstatic-jquery-ui
BuildRequires: python-xstatic-jsencrypt
BuildRequires: python-xstatic-qunit
BuildRequires: python-xstatic-rickshaw
BuildRequires: python-xstatic-spin
BuildRequires: python-django-pyscss
BuildRequires: python-scss
#end if

#for $i in $requires
Requires:         ${i}
#end for

#for $i in $conflicts
Conflicts:       ${i}
#end for

%description
Horizon is a Django application for providing Openstack UI components.
It allows performing site administrator (viewing account resource usage,
configuring users, accounts, quotas, flavors, etc.) and end user
operations (start/stop/delete instances, create/restore snapshots, view
instance VNC console, etc.)


%package -n openstack-dashboard
Summary:    Openstack web user interface reference implementation
Group:      Applications/System

%if ! 0%{?usr_only}
Requires:   httpd
Requires:   mod_wsgi
%endif
%if %{?with_compression} > 0
Requires:   python-lesscpy
%endif
Requires:   %{name} = %{epoch}:%{version}-%{release}

BuildRequires: python-devel
BuildRequires: python-django-openstack-auth
BuildRequires: python-django-compressor
BuildRequires: python-django-appconf
BuildRequires: python-lesscpy
BuildRequires: python-lockfile

%description -n openstack-dashboard
Openstack Dashboard is a web user interface for Openstack. The package
provides a reference implementation using the Django Horizon project,
mostly consisting of JavaScript and CSS to tie it altogether as a
standalone site.

%if ! 0%{?no_tests}
%package -n       python-%{python_name}-tests
Summary:          Tests for Horizon
Group:            Development/Libraries

Requires:         %{name} = %{epoch}:%{version}-%{release}
Requires:         openstack-dashboard = %{epoch}:%{version}-%{release}

# Test requirements:
#for $i in $test_requires
Requires:         ${i}
#end for

%description -n python-%{python_name}-tests
Horizon is a Django application for providing Openstack UI components.
It allows performing site administrator (viewing account resource usage,
configuring users, accounts, quotas, flavors, etc.) and end user
operations (start/stop/delete instances, create/restore snapshots, view
instance VNC console, etc.)

This package contains unit and functional tests for Horizon, with
simple runner (%{python_name}-make-test-env).
%endif

%if 0%{?with_doc}
%package doc
Summary:    Documentation for Django Horizon
Group:      Documentation

Requires:   %{name} = %{epoch}:%{version}-%{release}

BuildRequires: python-sphinx >= 1.1.3
# Doc building basically means we have to mirror Requires:
BuildRequires: python-dateutil
BuildRequires: python-glanceclient
BuildRequires: python-keystoneclient
BuildRequires: python-novaclient
BuildRequires: python-neutronclient
BuildRequires: python-cinderclient
BuildRequires: python-swiftclient

%description doc
Documentation for the Django Horizon application for talking with
Openstack
%endif

%prep
%setup -q -n horizon-%{os_version}
#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for

#raw
# remove unnecessary .mo files
# they will be generated later during package build
find . -name "django*.mo" -exec rm -f '{}' \;

# Don't access the net while building docs
sed -i '/sphinx.ext.intersphinx/d' doc/source/conf.py
#end raw

%if ! 0%{?usr_only}
#raw
sed -i -e 's@^BIN_DIR.*$@BIN_DIR = "/usr/bin"@' \
    -e 's@^LOGIN_URL.*$@LOGIN_URL = "/dashboard/auth/login/"@' \
    -e 's@^LOGOUT_URL.*$@LOGOUT_URL = "/dashboard/auth/logout/"@' \
    -e 's@^LOGIN_REDIRECT_URL.*$@LOGIN_REDIRECT_URL = "/dashboard"@' \
    -e 's@^DEBUG.*$@DEBUG = False@' \
    -e '/^COMPRESS_ENABLED.*$/a COMPRESS_OFFLINE = True' \
    openstack_dashboard/settings.py
#end raw

#if $newer_than_eq('2014.2')
%if 0%{?with_compression} > 0
#raw
# set COMPRESS_OFFLINE=True
sed -i 's:COMPRESS_OFFLINE.=.False:COMPRESS_OFFLINE = True:' openstack_dashboard/settings.py
#end raw
%else
#raw
# set COMPRESS_OFFLINE=False
sed -i 's:COMPRESS_OFFLINE = True:COMPRESS_OFFLINE = False:' openstack_dashboard/settings.py
#end raw
%endif
#end if

# Correct "local_settings.py.example" config file
#raw
sed -i -e 's@^#\?ALLOWED_HOSTS.*$@ALLOWED_HOSTS = ["horizon.example.com", "localhost"]@' \
    -e 's@^LOCAL_PATH.*$@LOCAL_PATH = "/tmp"@' \
    openstack_dashboard/local/local_settings.py.example
#end raw
%endif

#if $newer_than_eq('2014.2')
#raw
# make doc build compatible with python-oslo-sphinx RPM
sed -i 's/oslosphinx/oslo.sphinx/' doc/source/conf.py
#end raw
#end if

%build
#if $newer_than_eq('2014.2')
# compile message strings
cd horizon && django-admin compilemessages && cd ..
cd openstack_dashboard && django-admin compilemessages && cd ..
#end if

#raw
%{__python} setup.py build

cp openstack_dashboard/local/local_settings.py.example openstack_dashboard/local/local_settings.py
#end raw

#NOTE(aababilov): temporarily drop dependency on OpenStack client packages during RPM building
#if $older_than('2014.1')
mkdir tmp_settings
cp openstack_dashboard/settings.py* tmp_settings/
#raw
sed -i -e '/import exceptions/d' -e '/exceptions\./d' \
    -e '/import policy/d' -e '/policy\./d' \
    openstack_dashboard/settings.py
#end raw
#end if
#if $newer_than_eq('2014.1')
mkdir -p tmp_settings/utils
cp openstack_dashboard/settings.py* tmp_settings/
cp openstack_dashboard/utils/settings.py* tmp_settings/utils/settings.py
#raw
sed -i -e '/exceptions/d' openstack_dashboard/utils/settings.py
sed -i -e '/import exceptions/d' -e '/exceptions\.[A-Z][A-Z]/d' openstack_dashboard/settings.py
#end raw
#end if
#raw
%{__python} manage.py collectstatic --noinput
%if 0%{?with_compression} > 0
%{__python} manage.py compress --force
%endif
#end raw
#if $older_than('2014.1')
mv tmp_settings/* openstack_dashboard/
#end if
#if $newer_than_eq('2014.1')
mv tmp_settings/settings.py* openstack_dashboard/
mv tmp_settings/utils/settings.py* openstack_dashboard/utils/settings.py
#end if
rm -rf tmp_settings
#raw

export PYTHONPATH="$PWD:$PYTHONPATH"
%if 0%{?with_doc}
%if 0%{?rhel}==6
sphinx-1.0-build -b html doc/source html
%else
sphinx-build -b html doc/source html
%endif
# Fix hidden-file-or-dir warnings
rm -fr html/.doctrees html/.buildinfo
%endif
#end raw

%install
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

%if ! 0%{?usr_only}
# drop httpd-conf snippet
%if 0%{?rhel} || 0%{?fedora} <18
install -m 0644 -D -p %{SOURCE1} %{buildroot}%{_sysconfdir}/httpd/conf.d/openstack-dashboard.conf
%else
# httpd-2.4 changed the syntax
install -m 0644 -D -p %{SOURCE2} %{buildroot}%{_sysconfdir}/httpd/conf.d/openstack-dashboard.conf
%endif
%endif

install -d -m 755 %{buildroot}%{_datadir}/openstack-dashboard
install -d -m 755 %{buildroot}%{_sharedstatedir}/openstack-dashboard
install -d -m 755 %{buildroot}%{_sysconfdir}/openstack-dashboard

# Copy everything to /usr/share
mv %{buildroot}%{python_sitelib}/openstack_dashboard \
   %{buildroot}%{_datadir}/openstack-dashboard
cp manage.py %{buildroot}%{_datadir}/openstack-dashboard
rm -rf %{buildroot}%{python_sitelib}/openstack_dashboard

# remove unnecessary .po files
#raw
find %{buildroot} -name django.po -exec rm '{}' \;
find %{buildroot} -name djangojs.po -exec rm '{}' \;
#end raw

%if ! 0%{?usr_only}
# Move config to /etc, symlink it back to /usr/share
mv %{buildroot}%{_datadir}/openstack-dashboard/openstack_dashboard/local/local_settings.py.example %{buildroot}%{_sysconfdir}/openstack-dashboard/local_settings
ln -s %{_sysconfdir}/openstack-dashboard/local_settings %{buildroot}%{_datadir}/openstack-dashboard/openstack_dashboard/local/local_settings.py
%endif

# copy static files to %{_datadir}/openstack-dashboard/static
install -d -m 755 %{buildroot}%{_datadir}/openstack-dashboard/static
cp -a openstack_dashboard/static/* %{buildroot}%{_datadir}/openstack-dashboard/static
cp -a horizon/static/* %{buildroot}%{_datadir}/openstack-dashboard/static
cp -a static/* %{buildroot}%{_datadir}/openstack-dashboard/static

%if ! 0%{?no_tests}
install -d -m 755 %{buildroot}%{_bindir}
#include $part_fn("install_tests.sh")
%endif

%clean
rm -rf %{buildroot}

%files
%doc LICENSE README.rst
%dir %{python_sitelib}/horizon
%{python_sitelib}/horizon/*.py*
%{python_sitelib}/horizon/browsers
%{python_sitelib}/horizon/conf
%{python_sitelib}/horizon/contrib
%{python_sitelib}/horizon/forms
%{python_sitelib}/horizon/management
%{python_sitelib}/horizon/static
%{python_sitelib}/horizon/tables
%{python_sitelib}/horizon/tabs
%{python_sitelib}/horizon/templates
%{python_sitelib}/horizon/templatetags
%{python_sitelib}/horizon/test
%{python_sitelib}/horizon/utils
%{python_sitelib}/horizon/workflows
%{python_sitelib}/*.egg-info

%files -n openstack-dashboard
%dir %{_datadir}/openstack-dashboard/
%{_datadir}/openstack-dashboard/*.py*
%{_datadir}/openstack-dashboard/static
%{_datadir}/openstack-dashboard/openstack_dashboard/*.py*
%{_datadir}/openstack-dashboard/openstack_dashboard/api
%{_datadir}/openstack-dashboard/openstack_dashboard/conf
%dir %{_datadir}/openstack-dashboard/openstack_dashboard/dashboards/
%{_datadir}/openstack-dashboard/openstack_dashboard/dashboards/admin
%{_datadir}/openstack-dashboard/openstack_dashboard/dashboards/identity
%{_datadir}/openstack-dashboard/openstack_dashboard/dashboards/project
%{_datadir}/openstack-dashboard/openstack_dashboard/dashboards/router
%{_datadir}/openstack-dashboard/openstack_dashboard/dashboards/settings
%{_datadir}/openstack-dashboard/openstack_dashboard/dashboards/__init__.py*
%{_datadir}/openstack-dashboard/openstack_dashboard/django_pyscss_fix
%{_datadir}/openstack-dashboard/openstack_dashboard/enabled
%{_datadir}/openstack-dashboard/openstack_dashboard/local
%{_datadir}/openstack-dashboard/openstack_dashboard/management
%{_datadir}/openstack-dashboard/openstack_dashboard/openstack
%{_datadir}/openstack-dashboard/openstack_dashboard/static
%{_datadir}/openstack-dashboard/openstack_dashboard/templates
%{_datadir}/openstack-dashboard/openstack_dashboard/templatetags
%{_datadir}/openstack-dashboard/openstack_dashboard/test
%{_datadir}/openstack-dashboard/openstack_dashboard/usage
%{_datadir}/openstack-dashboard/openstack_dashboard/utils
%{_datadir}/openstack-dashboard/openstack_dashboard/wsgi
%dir %{_datadir}/openstack-dashboard/openstack_dashboard
%dir %{_datadir}/openstack-dashboard/openstack_dashboard/locale
%dir %{_datadir}/openstack-dashboard/openstack_dashboard/locale/??
%dir %{_datadir}/openstack-dashboard/openstack_dashboard/locale/??_??
%dir %{_datadir}/openstack-dashboard/openstack_dashboard/locale/??/LC_MESSAGES
%dir %{_datadir}/openstack-dashboard/openstack_dashboard/locale/??_??/LC_MESSAGES

%if ! 0%{?usr_only}
%{_sharedstatedir}/openstack-dashboard
%dir %attr(0750, root, apache) %{_sysconfdir}/openstack-dashboard
%config(noreplace) %{_sysconfdir}/httpd/conf.d/openstack-dashboard.conf
%config(noreplace) %attr(0640, root, apache) %{_sysconfdir}/openstack-dashboard/local_settings
%endif

%if ! 0%{?no_tests}
%files -n python-%{python_name}-tests
%{tests_data_dir}
%{_bindir}/%{python_name}-make-test-env
%endif

%if 0%{?with_doc}
%files doc
%doc html
%endif

%changelog
