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

# additional provides to be consistent with other django packages
Provides:   django-horizon = %{epoch}:%{version}-%{release}

BuildRequires: python-devel
BuildRequires: python-setuptools

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
Requires:   %{name} = %{epoch}:%{version}-%{release}

BuildRequires: python-devel

%description -n openstack-dashboard
Openstack Dashboard is a web user interface for Openstack. The package
provides a reference implementation using the Django Horizon project,
mostly consisting of JavaScript and CSS to tie it altogether as a standalone
site.

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
BuildRequires: python-quantumclient
BuildRequires: python-cinderclient
BuildRequires: python-swiftclient

%description doc
Documentation for the Django Horizon application for talking with Openstack
%endif

#raw
%prep
%setup -q -n horizon-%{os_version}

# Don't access the net while building docs
sed -i '/sphinx.ext.intersphinx/d' doc/source/conf.py

sed -i -e 's@^BIN_DIR.*$@BIN_DIR = "/usr/bin"@' \
    -e 's@^less_binary.*$@less_binary = "/usr/lib/node_modules/less/bin/lessc"@' \
    -e 's@^LOGIN_URL.*$@LOGIN_URL = "/dashboard/auth/login/"@' \
    -e 's@^LOGOUT_URL.*$@LOGOUT_URL = "/dashboard/auth/logout/"@' \
    -e 's@^LOGIN_REDIRECT_URL.*$@LOGIN_REDIRECT_URL = "/dashboard"@' \
    -e 's@^DEBUG.*$@DEBUG = False@' \
    openstack_dashboard/settings.py

# remove unnecessary .po files
find . -name "django*.po" -exec rm -f '{}' \;

%build
%{__python} setup.py build

%install
rm -rf %{buildroot}

%{__python} setup.py install -O1 --skip-build --root %{buildroot}

# drop httpd-conf snippet
%if 0%{?rhel} || 0%{?fedora} <18
install -m 0644 -D -p %{SOURCE1} %{buildroot}%{_sysconfdir}/httpd/conf.d/openstack-dashboard.conf
%else
# httpd-2.4 changed the syntax
install -m 0644 -D -p %{SOURCE2} %{buildroot}%{_sysconfdir}/httpd/conf.d/openstack-dashboard.conf
%endif

export PYTHONPATH="$PWD:$PYTHONPATH"
%if 0%{?with_doc}
%if 0%{?rhel}==6
sphinx-1.0-build -b html doc/source html
%else
sphinx-build -b html doc/source html
%endif
%endif

# Fix hidden-file-or-dir warnings
rm -fr html/.doctrees html/.buildinfo

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

# copy static files to %{_datadir}/openstack-dashboard/static
mkdir -p %{buildroot}%{_datadir}/openstack-dashboard/static
cp -a openstack_dashboard/static/* %{buildroot}%{_datadir}/openstack-dashboard/static
cp -a horizon/static/* %{buildroot}%{_datadir}/openstack-dashboard/static

# compress css, js etc.
cd %{buildroot}%{_datadir}/openstack-dashboard
# TODO(aababilov): compress them
#%{__python} manage.py collectstatic --noinput --pythonpath=../../lib/python2.7/site-packages/
#%{__python} manage.py compress --pythonpath=../../lib/python2.7/site-packages/

node_less_dir=%{buildroot}/usr/lib/node_modules/less
mkdir -p "$node_less_dir"
mv %{buildroot}%{python_sitelib}/bin/less "$node_less_dir/bin"
mv %{buildroot}%{python_sitelib}/bin/lib "$node_less_dir/lib"
rm -rf %{buildroot}%{python_sitelib}/bin/

%clean
rm -rf %{buildroot}


%files
%doc LICENSE README.rst
%{python_sitelib}/*
/usr/lib/node_modules/less


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
#end raw
