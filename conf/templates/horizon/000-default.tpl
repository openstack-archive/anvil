#From commit b32c876ed5e66c8971c8126432c1ae957301eb08 of devstack.sh repo.
#
#With adjustments to make HORIZON_PORT, ERROR_LOG, ACCESS_LOG, VPN_DIR a param

<VirtualHost *:%HORIZON_PORT%>
    WSGIScriptAlias / %HORIZON_DIR%/openstack_dashboard/wsgi/django.wsgi
    WSGIDaemonProcess horizon user=%USER% group=%GROUP% processes=3 threads=10
    SetEnv APACHE_RUN_USER %USER%
    SetEnv APACHE_RUN_GROUP %GROUP%
    WSGIProcessGroup horizon

    DocumentRoot %HORIZON_DIR%/.blackhole/
    Alias /media %HORIZON_DIR%/openstack_dashboard/static
    Alias /vpn %VPN_DIR%

    <Directory />
        Options FollowSymLinks
        AllowOverride None
    </Directory>

    <Directory %HORIZON_DIR%/>
        Options Indexes FollowSymLinks MultiViews
        AllowOverride None
        Order allow,deny
        allow from all
    </Directory>

    ErrorLog %ERROR_LOG%
    LogLevel warn
    CustomLog %ACCESS_LOG% combined

</VirtualHost>

