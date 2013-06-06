.. _solved-problems:

===============
Solved Problems
===============

MySQL user denied
-----------------

This seems common and can be fixed by running one of the steps at
http://dev.mysql.com/doc/refman/5.0/en/resetting-permissions.html

The temporary folder for building (/tmp/XYZ) is not owned by your user!
-----------------------------------------------------------------------

This is a new feature of pip>=1.3 where it seems to incorrectly handle the SUDO
user. To get around this just remove the above directory and reactivate the
appropriate ANVIL command.
