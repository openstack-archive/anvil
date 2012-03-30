===============
Known Issues
===============


Ubuntu 11.10 (Oneiric Ocelot)
-----------------------------

-  Resetting/cleaning up the network on uninstall doesn’t seem to be
   *100%* correct

RHEL 6.2
--------

-  *numpy* (for novnc) pulls in *python-nose* which we are installing
   from *EPEL* and *symlinking* so that we don’t have to modify github
   code directly but the *numpy* dependency can’t be installed with the
   previous symlink. We are currently just using *pip* to fix this.
-  Fixing up the network on uninstall doesn’t seem to be 100% correct
-  I (josh) dont really like how we have to edit the *httpd.conf* to use
   the current sudo user. Without this though it doesn’t seem like
   *python-wsgi* can access the users libraries that are downloaded and
   other files can’t be accessed either. This could be solved by having
   a new user and group and doing what devstack v1.0 does (but this
   seems like overkill).

Others
------

Any other piece of code with a *TODO* probably should be looked at...
