========
Features
========

-  Supports more than one distribution.

   -  Currently RHEL 6.2 (with `epel`_), Ubuntu 11.10, Fedora 16, Ubuntu 12.10 (seems to work)

-  Supports dry-run mode (to see what *would* happen)
-  Supports varying installation *personas*
-  A single ``anvil.ini`` file that shows common configuration
-  Supports install/uninstall/starting/stopping of OpenStack components.

   -  In various styles (daemonizing via `forking`_, `screen`_, `upstart`_)

-  Written in python so it matches the style of other `OpenStack`_ components.
-  Extensively documented distribution specifics

   -  Packages and pip (with versions known to work!) dependencies
   -  Any needed distribution specific actions (ie service names…)

-  Follows standard software development practices (for everyones sanity).

   -  Functions, classes, objects and more (oh my!)
   -  Still *readable* by someone with limited python knowledge.

-  The ability to be unit-tested!
-  Extensive logging

.. _epel: http://fedoraproject.org/wiki/EPEL
.. _forking: http://users.telenet.be/bartl/classicperl/fork/all.html
.. _screen: http://www.manpagez.com/man/1/screen/
.. _upstart: http://upstart.ubuntu.com/
.. _OpenStack: http://openstack.org/
