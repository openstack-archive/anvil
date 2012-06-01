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

Mysql unknown instance
----------------------

This seems to happen sometimes with the following exception:

::

     ProcessExecutionError: None
     Command: service mysql restart
     Exit code: 1
     Stdout: ''
     Stderr: 'restart: Unknown instance: \n'

     
To resolve this the following seems to work:

::

    MYSQL_PKGS=`sudo dpkg --get-selections | grep mysql | cut -f 1`
    echo $MYSQL_PKGS
    sudo apt-get remove --purge $MYSQL_PKGS


Libguestfs not syncing
---------------------

On RHEL 6.2 people have seen files not being synced when the temporary file location is unmounted.

Getting a newer version of libguestfs seems to help. To do this follow the ``README`` at
http://people.redhat.com/~rjones/libguestfs-RHEL-6.3-preview/. Hopefully this will not be a problem
on RHEL 6.3.

Then run:

::

     sudo yum -y install libguestfs* guestfs*


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
