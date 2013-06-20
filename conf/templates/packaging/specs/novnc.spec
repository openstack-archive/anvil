
%global os_version $version

Name:           novnc
Summary:        VNC client using HTML5 (Web Sockets, Canvas) with encryption support
Epoch:          $epoch
Version:        %{os_version}$version_suffix
Release:        $release%{?dist}

License:        GPLv3
URL:            https://github.com/kanaka/noVNC
Source0:        novnc-%{os_version}.tar.gz
Source1:        openstack-nova-novncproxy.init
Source2:        nova-novncproxy.1
Source3:        novnc_server.1

#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

#raw
BuildArch:      noarch
BuildRequires:  python2-devel

Requires:       python-websockify

%description
Websocket implementation of VNC client


%package -n openstack-nova-novncproxy
Summary:        Proxy server for noVNC traffic over Websockets
Requires:       novnc
Requires:       openstack-nova
Requires:       python-websockify

Requires(post): chkconfig
Requires(preun): chkconfig
Requires(preun): initscripts

%description -n openstack-nova-novncproxy
OpenStack Nova noVNC server that proxies VNC traffic over Websockets.

%prep
%setup -q -n %{name}-%{os_version}
#end raw
#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for
#raw

# call the websockify executable
sed -i 's/wsproxy\.py/websockify/' utils/launch.sh
# import websockify
sed -i 's/import wsproxy/import wsproxy as websockify/' utils/nova-novncproxy
install %{SOURCE2} %{SOURCE3} docs/

%build


%install
mkdir -p %{buildroot}/%{_usr}/share/novnc/utils
install -m 444 *html %{buildroot}/%{_usr}/share/novnc
#provide an index file to prevent default directory browsing
install -m 444 vnc.html %{buildroot}/%{_usr}/share/novnc/index.html

mkdir -p %{buildroot}/%{_usr}/share/novnc/include/
install -m 444 include/*.*  %{buildroot}/%{_usr}/share/novnc/include
mkdir -p %{buildroot}/%{_usr}/share/novnc/images
install -m 444 images/*.*  %{buildroot}/%{_usr}/share/novnc/images

mkdir -p %{buildroot}/%{_bindir}
install utils/launch.sh  %{buildroot}/%{_bindir}/novnc_server

install utils/nova-novncproxy %{buildroot}/%{_bindir}

mkdir -p %{buildroot}%{_mandir}/man1/
install -m 444 docs/novnc_server.1 %{buildroot}%{_mandir}/man1/

mkdir -p %{buildroot}%{_initddir}
install -p -D -m 755 %{SOURCE1} %{buildroot}%{_initrddir}/openstack-nova-novncproxy


%preun -n openstack-nova-novncproxy
if [ $1 -eq 0 ] ; then
    /sbin/service openstack-nova-novncproxy stop >/dev/null 2>&1
    /sbin/chkconfig --del openstack-nova-novncproxy
fi


%files
%doc README.md LICENSE.txt

%dir %{_usr}/share/novnc
%{_usr}/share/novnc/*.*
%dir %{_usr}/share/novnc/include
%{_usr}/share/novnc/include/*
%dir %{_usr}/share/novnc/images
%{_usr}/share/novnc/images/*
%{_bindir}/novnc_server
%{_mandir}/man1/novnc_server.1*


%files -n openstack-nova-novncproxy
%{_bindir}/nova-novncproxy
%{_initrddir}/openstack-nova-novncproxy

%changelog
#endraw
