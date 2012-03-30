.. _solved-problems:

===============
Solved Problems
===============


Solutions
=========

Mysql user denied
-----------------

This seems common and can be fixed by running one of the steps at
http://dev.mysql.com/doc/refman/5.0/en/resetting-permissions.html

Horizon dead on start
---------------------

If you get the following (when starting *horizon*) in ubuntu 11.10:

::

     .: 51: Can't open /etc/apache2/envvars

Run:

::

     APACHE_PKGS=`sudo dpkg --get-selections | grep apache | cut -f 1`
     echo $APACHE_PKGS
     sudo apt-get remove --purge $APACHE_PKGS

Then stop and uninstall and install to resolve this.
