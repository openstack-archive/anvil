%global python_name heat
%global daemon_prefix openstack-heat
%global os_version ${version}

%global with_doc %{!?_without_doc:1}%{?_without_doc:0}

#TODO: Get heat to build with docs.  It currently reuiqres over 15 packages/buildrequires to build just the docs.  Punting for now due to insanity.
%if ! (0%{?fedora} > 12 || 0%{?rhel} > 5)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

%if ! 0%{?overwrite_configs}
%global configfile %config(noreplace)
%else
%global configfile %verify(mode)
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

%if ! (0%{?rhel} > 6)
Source10:         openstack-heat-api.init
Source11:         openstack-heat-api-cfn.init
Source12:         openstack-heat-engine.init
Source13:         openstack-heat-api-cloudwatch.init
%else
Source10:         openstack-heat-api.service
Source11:         openstack-heat-api-cfn.service
Source12:         openstack-heat-engine.service
Source13:         openstack-heat-api-cloudwatch.service
%endif

Source20:         heat.logrotate

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

%build

export PBR_VERSION=$version
%{__python} setup.py build

%install

export PBR_VERSION=$version
%{__python} setup.py install -O1 --skip-build --root=%{buildroot}

#raw
%if ! 0%{?usr_only}
mkdir -p %{buildroot}/var/log/heat/
mkdir -p %{buildroot}/var/run/heat/

# install init files
%if ! (0%{?rhel} > 6)
install -p -D -m 755 %{SOURCE10} %{buildroot}%{_initrddir}/openstack-heat-api
install -p -D -m 755 %{SOURCE11} %{buildroot}%{_initrddir}/openstack-heat-api-cfn
install -p -D -m 755 %{SOURCE12} %{buildroot}%{_initrddir}/openstack-heat-engine
install -p -D -m 755 %{SOURCE13} %{buildroot}%{_initrddir}/openstack-heat-api-cloudwatch
%else
install -p -D -m 755 %{SOURCE10} %{buildroot}%{_unitdir}/openstack-heat-api.service
install -p -D -m 755 %{SOURCE11} %{buildroot}%{_unitdir}/openstack-heat-api-cfn.service
install -p -D -m 755 %{SOURCE12} %{buildroot}%{_unitdir}/openstack-heat-engine.service
install -p -D -m 755 %{SOURCE13} %{buildroot}%{_unitdir}/openstack-heat-api-cloudwatch.service
%endif

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
%endif
rm -f %{buildroot}/usr/bin/cinder-keystone-setup
%if ! 0%{?usr_only}

#end raw

#raw
install -p -D -m 640 etc/heat/api-paste.ini %{buildroot}/%{_sysconfdir}/heat/api-paste.ini
install -p -D -m 640 etc/heat/policy.json %{buildroot}/%{_sysconfdir}/heat/policy.json
install -p -D -m 640 %{SOURCE20} %{buildroot}/%{_sysconfdir}/logrotate.d/heat
#end raw
%endif

%package common
Summary:         Heat common
Group:           System Environment/Base

#for $i in $requires
Requires:         ${i}
#end for

%if ! 0%{?usr_only}
Requires(pre):   shadow-utils
%endif

#for $i in $conflicts
Conflicts:       ${i}
#end for

%description common
Components common to all OpenStack Heat services

%files common
%doc LICENSE
%{_bindir}/heat-db-setup
%{_bindir}/heat-keystone-setup
%{_bindir}/heat-keystone-setup-domain
%{_bindir}/heat-manage
%{python_sitelib}/heat*
%if ! 0%{?usr_only}
%dir %attr(0755,heat,root) %{_localstatedir}/log/heat
%dir %attr(0755,heat,root) %{_sharedstatedir}/heat
%dir %attr(0755,heat,root) %{_sysconfdir}/heat
%dir %attr(0755,heat,root) /var/run/heat
%configfile %attr(0640, root, heat) %{_sysconfdir}/heat/api-paste.ini
%configfile %attr(0640, root, heat) %{_sysconfdir}/heat/policy.json
%configfile %{_sysconfdir}/logrotate.d/heat
%endif

%if ! 0%{?usr_only}
%pre common
# 187:187 for heat - rhbz#845078
getent group heat >/dev/null || groupadd -r --gid 187 heat
getent passwd heat  >/dev/null || \
useradd --uid 187 -r -g heat -d %{_sharedstatedir}/heat -s /sbin/nologin \
-c "OpenStack Heat Daemons" heat
exit 0
%endif

%package engine
Summary:         The Heat engine
Group:           System Environment/Base

Requires:        %{name}-common = %{version}-%{release}

%description engine
OpenStack API for starting CloudFormation templates on OpenStack

%files engine
%doc README.rst LICENSE
%{_bindir}/heat-engine
%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/openstack-heat-engine
%else
%{_unitdir}/openstack-heat-engine.service
%endif
%endif

%if 0%{?rhel} > 6
%post engine
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-engine.service
fi

%preun engine
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-engine.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-engine.service > /dev/null 2>&1 || :
fi

%postun engine
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-engine.service #>/dev/null 2>&1 || :
fi
%endif


%package api
Summary: The Heat API
Group: System Environment/Base

Requires: %{name}-common = %{version}-%{release}

%description api
OpenStack-native ReST API to the Heat Engine

%files api
%doc README.rst LICENSE
%{_bindir}/heat-api
%configfile %attr(-, root, glance) %{_bindir}/heat-wsgi-api
%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/openstack-heat-api
%else
%{_unitdir}/openstack-heat-api.service
%endif
%endif

%if 0%{?rhel} > 6
%post api
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-api.service
fi

%preun api
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-api.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-api.service > /dev/null 2>&1 || :
fi

%postun api
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-api.service #>/dev/null 2>&1 || :
fi
%endif


%package api-cfn
Summary: Heat CloudFormation API
Group: System Environment/Base

Requires: %{name}-common = %{version}-%{release}

%description api-cfn
AWS CloudFormation-compatible API to the Heat Engine

%files api-cfn
%doc README.rst LICENSE
%{_bindir}/heat-api-cfn
%configfile %attr(-, root, glance) %{_bindir}/heat-wsgi-api-cfn
%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/openstack-heat-api-cfn
%else
%{_unitdir}/openstack-heat-api-cfn.service
%endif
%endif

%if 0%{?rhel} > 6
%post api-cfn
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-api-cfn.service
fi

%preun api-cfn
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-api-cfn.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-api-cfn.service > /dev/null 2>&1 || :
fi

%postun api-cfn
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-api-cfn.service #>/dev/null 2>&1 || :
fi
%endif


%package api-cloudwatch
Summary: Heat CloudWatch API
Group: System Environment/Base

Requires: %{name}-common = %{version}-%{release}


%description api-cloudwatch
AWS CloudWatch-compatible API to the Heat Engine

%files api-cloudwatch
%{_bindir}/heat-api-cloudwatch
%configfile %attr(-, root, glance) %{_bindir}/heat-wsgi-api-cloudwatch
%if ! 0%{?usr_only}
%if ! (0%{?rhel} > 6)
%{_initrddir}/openstack-heat-api-cloudwatch
%else
%{_unitdir}/openstack-heat-api-cloudwatch.service
%endif
%endif

%if 0%{?rhel} > 6
%post api-cloudwatch
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-api-cloudwatch.service
fi

%preun api-cloudwatch
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-api-cloudwatch.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-api-cloudwatch.service > /dev/null 2>&1 || :
fi

%postun api-cloudwatch
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-api-cloudwatch.service #>/dev/null 2>&1 || :
fi
%endif

%changelog
