%global python_name heat
%global daemon_prefix openstack-heat
%global os_version ${version}

%global with_doc %{!?_without_doc:1}%{?_without_doc:0}

#TODO: Get heat to build with docs.  It currently reuiqres over 15 packages/buildrequires to build just the docs.  Punting for now due to insanity.
%if ! (0%{?fedora} > 12 || 0%{?rhel} > 5)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

Name:             openstack-heat
Summary:          OpenStack Orchestration (heat)
Version:          %{os_version}$version_suffix
Release:          $release%{?dist}

License:          ASL 2.0
Group:            System Environment/Base
Vendor:           Openstack Foundation
URL:              http://www.openstack.org
Source0:          %{python_name}-%{os_version}.tar.gz

Source10:         openstack-heat-api.init
Source11:         openstack-heat-api-cfn.init
Source12:         openstack-heat-engine.init
Source13:         openstack-heat-api-cloudwatch.init

Source20:         heat.conf
Source21:         heat-api-paste.ini
Source22:         heat.logrotate

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}

BuildArch:        noarch
BuildRequires:    python2-devel
BuildRequires:    python-setuptools
BuildRequires:    python-sphinx
BuildRequires:    python-pbr

Requires:         %{name}-common = %{version}-%{release}
Requires:         %{name}-engine = %{version}-%{release}
Requires:         %{name}-api = %{version}-%{release}
Requires:         %{name}-api-cfn = %{version}-%{release}
Requires:         %{name}-api-cloudwatch = %{version}-%{release}

%description
Heat provides AWS CloudFormation and CloudWatch functionality for OpenStack.

%prep
%setup -q -n %{python_name}-%{os_version}

#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for

#raw
%build
%{__python} setup.py build

%install
%{__python} setup.py install -O1 --skip-build --root=%{buildroot}
sed -i -e '/^#!/,1 d' %{buildroot}/%{python_sitelib}/heat/db/sqlalchemy/manage.py
sed -i -e '/^#!/,1 d' %{buildroot}/%{python_sitelib}/heat/db/sqlalchemy/migrate_repo/manage.py
mkdir -p %{buildroot}/var/log/heat/
mkdir -p %{buildroot}/var/run/heat/

# install init files
install -p -D -m 755 %{SOURCE10} %{buildroot}%{_initrddir}/openstack-heat-api
install -p -D -m 755 %{SOURCE11} %{buildroot}%{_initrddir}/openstack-heat-api-cfn
install -p -D -m 755 %{SOURCE12} %{buildroot}%{_initrddir}/openstack-heat-engine
install -p -D -m 755 %{SOURCE13} %{buildroot}%{_initrddir}/openstack-heat-api-cloudwatch

mkdir -p %{buildroot}/var/lib/heat/
mkdir -p %{buildroot}/etc/heat/

#export PYTHONPATH="$PWD:$PYTHONPATH"
#pushd doc
#sphinx-1.0-build -b html -d build/doctrees source build/html
#sphinx-1.0-build -b man -d build/doctrees source build/man
#mkdir -p %{buildroot}%{_mandir}/man1
#install -p -D -m 644 build/man/*.1 %{buildroot}%{_mandir}/man1/
#popd

rm -rf %{buildroot}/var/lib/heat/.dummy
rm -f %{buildroot}/usr/bin/cinder-keystone-setup

install -p -D -m 640 %{SOURCE20} %{buildroot}/%{_sysconfdir}/heat/heat.conf
install -p -D -m 640 %{SOURCE21} %{buildroot}/%{_sysconfdir}/heat/heat-api-paste.ini
install -p -D -m 640 %{SOURCE22} %{buildroot}/%{_sysconfdir}/logrotate.d/heat
#end raw

%package common
Summary:         Heat common
Group:           System Environment/Base

#for $i in $requires
Requires:         ${i}
#end for

Requires(pre):   shadow-utils

%description common
Components common to all OpenStack Heat services

%files common
%doc LICENSE
%{_bindir}/heat-db-setup
%{_bindir}/heat-keystone-setup
%{_bindir}/heat-manage
%{python_sitelib}/heat*
%dir %attr(0755,heat,root) %{_localstatedir}/log/heat
%dir %attr(0755,heat,root) %{_sharedstatedir}/heat
%dir %attr(0755,heat,root) %{_sysconfdir}/heat
%dir %attr(0755,heat,root) /var/run/heat
%config(noreplace) %{_sysconfdir}/heat/heat.conf
%config(noreplace)/%{_sysconfdir}/heat/heat-api-paste.ini
%config(noreplace) %{_sysconfdir}/logrotate.d/heat

%pre common
# 187:187 for heat - rhbz#845078
getent group heat >/dev/null || groupadd -r --gid 187 heat
getent passwd heat  >/dev/null || \
useradd --uid 187 -r -g heat -d %{_sharedstatedir}/heat -s /sbin/nologin \
-c "OpenStack Heat Daemons" heat
exit 0

%package engine
Summary:         The Heat engine
Group:           System Environment/Base

Requires:        %{name}-common = %{version}-%{release}

%description engine
OpenStack API for starting CloudFormation templates on OpenStack

%files engine
%doc README.rst LICENSE
%{_bindir}/heat-engine
%{_initrddir}/openstack-heat-engine

%package api
Summary: The Heat API
Group: System Environment/Base

Requires: %{name}-common = %{version}-%{release}

%description api
OpenStack-native ReST API to the Heat Engine

%files api
%doc README.rst LICENSE
%{_bindir}/heat-api
%{_initrddir}/openstack-heat-api

%package api-cfn
Summary: Heat CloudFormation API
Group: System Environment/Base

Requires: %{name}-common = %{version}-%{release}

%description api-cfn
AWS CloudFormation-compatible API to the Heat Engine

%files api-cfn
%doc README.rst LICENSE
%{_bindir}/heat-api-cfn
%{_initrddir}/openstack-heat-api-cfn


%package api-cloudwatch
Summary: Heat CloudWatch API
Group: System Environment/Base

Requires: %{name}-common = %{version}-%{release}


%description api-cloudwatch
AWS CloudWatch-compatible API to the Heat Engine

%files api-cloudwatch
%{_bindir}/heat-api-cloudwatch
%{_initrddir}/openstack-heat-api-cloudwatch

%changelog
