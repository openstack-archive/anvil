<VirtualHost *:%HORIZON_PORT%>

#From commit 30439a6dc4
#With adjustments to make APACHE_RUN_GROUP a param
#and to make HORIZON_PORT a param

    WSGIScriptAlias / %HORIZON_DIR%/openstack-dashboard/dashboard/wsgi/django.wsgi
    WSGIDaemonProcess horizon user=%USER% group=%GROUP% processes=3 threads=10
    SetEnv APACHE_RUN_USER %USER%
    SetEnv APACHE_RUN_GROUP %GROUP%
    WSGIProcessGroup horizon

    DocumentRoot %HORIZON_DIR%/.blackhole/
    Alias /media %HORIZON_DIR%/openstack-dashboard/dashboard/static
    Alias /vpn /opt/stack/vpn

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

    ErrorLog /var/log/apache2/error.log
    LogLevel warn
    CustomLog /var/log/apache2/access.log combined

</VirtualHost>

