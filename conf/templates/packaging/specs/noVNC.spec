%if ! (0%{?fedora} > 12 || 0%{?rhel} > 5)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

Name:             openstack-noVNC
Summary:          OpenStack Nova VNC console service
Version:          $version
Release:          1%{?dist}
Epoch:            $epoch

Group:            Applications/System
License:          LGPL v3 with exceptions
Vendor:           OpenStack Foundation
URL:              https://github.com/openstack/noVNC
Source0:          %{name}-%{version}.tar.gz

Requires:         numpy
BuildRequires:    gcc
BuildRequires:    make


%description
noVNC is a VNC client written using HTML5 (Web Sockets, Canvas) with encryption (wss://) support.


%prep
%setup -q


%build
make -C utils rebind.so


%install
TARGET_DIR=%{buildroot}/usr/share/novnc
install -p -d -m 755 $TARGET_DIR $TARGET_DIR/utils %{buildroot}%{python_sitelib}
cp -a include $TARGET_DIR
install -m 644 images/favicon.ico vnc{,_auto}.html $TARGET_DIR
cp -a utils/{launch.sh,websockify,websocket.py,wsproxy.py,rebind.so} $TARGET_DIR/utils

for i in websocket.py wsproxy.py; do
    ln -s /usr/share/novnc/utils/$i %{buildroot}%{python_sitelib}/$i
done

install -p -D -m 755 utils/nova-novncproxy %{buildroot}/usr/bin/nova-novncproxy
install -p -D -m 755 redhat/nova-novncproxy.init %{buildroot}%{_initrddir}/nova-novncproxy


%clean
rm -rf %{buildroot}


%preun
if [ $1 -eq 0 ] ; then
    /sbin/service nova-novncproxy stop >/dev/null 2>&1
fi


%postun
if [ $1 -eq 1 ] ; then
    /sbin/service nova-novncproxy condrestart
fi


%files
%doc LICENSE* README*
%{_usr}/share/novnc
%{_usr}/bin/*
%{python_sitelib}/*
%{_initrddir}/*


%changelog
