===============
Known Issues
===============


Ubuntu 11.10 (Oneiric Ocelot)
-----------------------------

-  Resetting/cleaning up the network on uninstall doesn’t seem to be
   *100%* correct
   
There is a script in ``tools/clear-net-ubuntu.sh`` that might help with this.

RHEL 6.2
--------

-  *numpy* (for novnc) pulls in *python-nose* which we are installing
   from *EPEL* and *symlinking* so that we don’t have to modify github
   code directly but the *numpy* dependency can’t be installed with the
   previous symlink. We are currently just using *pip* to fix this.
-  Fixing up the network on uninstall doesn’t seem to be 100% correct

We might need a script like the ``tools/clear-net-ubuntu.sh`` to help in this situation.

Others
------

Any other piece of code with a *TODO* probably should be looked at...
