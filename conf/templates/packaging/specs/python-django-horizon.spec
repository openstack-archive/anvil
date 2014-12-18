#encoding UTF-8
# Based on spec by:
# * Matthias Runge <mrunge@redhat.com>
# * Pádraig Brady <P@draigBrady.com>
# * Alan Pevec <apevec@redhat.com>
# * Cole Robinson <crobinso@redhat.com>

%global os_version $version

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

%description
Horizon is a Django application for providing Openstack UI components.
It allows performing site administrator (viewing account resource usage,
configuring users, accounts, quotas, flavors, etc.) and end user
operations (start/stop/delete instances, create/restore snapshots, view
instance VNC console, etc.)


%package -n openstack-dashboard
Summary:    Openstack web user interface reference implementation
Group:      Applications/System

Requires:   httpd
Requires:   mod_wsgi
Requires:   python-lesscpy
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

# Don't access the net while building docs
sed -i '/sphinx.ext.intersphinx/d' doc/source/conf.py

sed -i -e 's@^BIN_DIR.*$@BIN_DIR = "/usr/bin"@' \
    -e 's@^LOGIN_URL.*$@LOGIN_URL = "/dashboard/auth/login/"@' \
    -e 's@^LOGOUT_URL.*$@LOGOUT_URL = "/dashboard/auth/logout/"@' \
    -e 's@^LOGIN_REDIRECT_URL.*$@LOGIN_REDIRECT_URL = "/dashboard"@' \
    -e 's@^DEBUG.*$@DEBUG = False@' \
    -e '/^COMPRESS_ENABLED.*$/a COMPRESS_OFFLINE = True' \
    openstack_dashboard/settings.py

#if $newer_than_eq('2014.2')
#Enable offline compression
sed -i 's:COMPRESS_OFFLINE.=.False:COMPRESS_OFFLINE = True:' openstack_dashboard/settings.py
#end if

# Correct "local_settings.py.example" config file
sed -i -e 's@^#\?ALLOWED_HOSTS.*$@ALLOWED_HOSTS = ["horizon.example.com", "localhost"]@' \
    -e 's@^LOCAL_PATH.*$@LOCAL_PATH = "/tmp"@' \
    openstack_dashboard/local/local_settings.py.example

# remove unnecessary .po files
find . -name "django*.po" -exec rm -f '{}' \;

#if $newer_than_eq('2014.2')
# make doc build compatible with python-oslo-sphinx RPM
sed -i 's/oslosphinx/oslo.sphinx/' doc/source/conf.py
#end if

%build

#if $newer_than_eq('2014.2')
%if 0%{?rhel}==6
cd horizon && django-admin.py compilemessages && cd ..
cd openstack_dashboard && django-admin.py compilemessages && cd ..
%else
cd horizon && django-admin compilemessages && cd ..
cd openstack_dashboard && django-admin compilemessages && cd ..
%endif
#end if

%{__python} setup.py build

cp openstack_dashboard/local/local_settings.py.example openstack_dashboard/local/local_settings.py

#NOTE(aababilov): temporarily drop dependency on OpenStack client packages during RPM building
#end raw
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
%{__python} manage.py compress --force
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

# drop httpd-conf snippet
%if 0%{?rhel} || 0%{?fedora} <18
install -m 0644 -D -p %{SOURCE1} %{buildroot}%{_sysconfdir}/httpd/conf.d/openstack-dashboard.conf
%else
# httpd-2.4 changed the syntax
install -m 0644 -D -p %{SOURCE2} %{buildroot}%{_sysconfdir}/httpd/conf.d/openstack-dashboard.conf
%endif

install -d -m 755 %{buildroot}%{_datadir}/openstack-dashboard
install -d -m 755 %{buildroot}%{_sharedstatedir}/openstack-dashboard
install -d -m 755 %{buildroot}%{_sysconfdir}/openstack-dashboard

# Copy everything to /usr/share
mv %{buildroot}%{python_sitelib}/openstack_dashboard \
   %{buildroot}%{_datadir}/openstack-dashboard
mv manage.py %{buildroot}%{_datadir}/openstack-dashboard
rm -rf %{buildroot}%{python_sitelib}/openstack_dashboard

# Move config to /etc, symlink it back to /usr/share
mv %{buildroot}%{_datadir}/openstack-dashboard/openstack_dashboard/local/local_settings.py.example %{buildroot}%{_sysconfdir}/openstack-dashboard/local_settings
ln -s %{_sysconfdir}/openstack-dashboard/local_settings %{buildroot}%{_datadir}/openstack-dashboard/openstack_dashboard/local/local_settings.py

#if $older_than('2014.2')
%if 0%{?rhel} > 6 || 0%{?fedora} >= 16
%find_lang django
%find_lang djangojs
%else
# Handling locale files
# This is adapted from the %%find_lang macro, which cannot be directly
# used since Django locale files are not located in %%{_datadir}
#
# The rest of the packaging guideline still apply -- do not list
# locale files by hand!
(cd $RPM_BUILD_ROOT && find . -name 'django*.mo') | %{__sed} -e 's|^.||' |
%{__sed} -e \
   's:\(.*/locale/\)\([^/_]\+\)\(.*\.mo$\):%lang(\2) \1\2\3:' \
      >> django.lang
%endif

grep "\/usr\/share\/openstack-dashboard" django.lang > dashboard.lang
grep "\/site-packages\/horizon" django.lang > horizon.lang

%if 0%{?rhel} > 6 || 0%{?fedora} >= 16
cat djangojs.lang >> horizon.lang
%endif
#end if

# copy static files to %{_datadir}/openstack-dashboard/static
install -d -m 755 %{buildroot}%{_datadir}/openstack-dashboard/static
cp -a openstack_dashboard/static/* %{buildroot}%{_datadir}/openstack-dashboard/static
cp -a horizon/static/* %{buildroot}%{_datadir}/openstack-dashboard/static
cp -a static/* %{buildroot}%{_datadir}/openstack-dashboard/static

%clean
rm -rf %{buildroot}

%files
%doc LICENSE README.rst
%{python_sitelib}/*


%files -n openstack-dashboard
%{_datadir}/openstack-dashboard/

%{_sharedstatedir}/openstack-dashboard
%dir %attr(0750, root, apache) %{_sysconfdir}/openstack-dashboard
%config(noreplace) %{_sysconfdir}/httpd/conf.d/openstack-dashboard.conf
%config(noreplace) %attr(0640, root, apache) %{_sysconfdir}/openstack-dashboard/local_settings


%if 0%{?with_doc}
%files doc
%doc html
%endif

%changelog
