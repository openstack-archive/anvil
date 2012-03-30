|DEVSTACKpy| is a set of **python** scripts and utilities to quickly
deploy an OpenStack cloud.

It is meant to be a full re-write of `DEVSTACK`_ which adds more
developer features (it is **not** meant to be a full deployment
system!).

Index
=====

-  `Beginners guide`_
-  `Examples`_
-  `Bugs, hugs and code`_
-  `Q+A`_
-  `Solved problems/workarounds`_
-  Advanced

   -  `Hacking`_
   -  `Adding your own distro`_
   -  `Adding your own persona`_
   -  `Design details`_
   -  `Known issues`_

Goals
=====

-  To aid developers getting involved with OpenStack!
-  To quickly build developer OpenStack environments in a clean
   environment (as well as start, stop, and uninstall those
   environments) with as little baggage as possible.
-  To describe working configurations of OpenStack.

   -  Which code branches work together?
   -  What do config files look like for those branches?
   -  What packages are needed for installation for a given
      distribution?

-  To make it easier for developers to dive into OpenStack so that they
   can productively contribute without having to understand every part
   of the system at once.
-  To make it easy to prototype cross-project features.

Features
========

-  Supports more than one distribution.
-  Currently RHEL 6.2 (with `epel`_), Ubuntu 11.10, Fedora 16
-  Supports dry-run mode (to see what *would* happen)
-  Supports varying installation *personas*
-  See ``conf/personas/devstack.sh.yaml``
-  A single ``stack.ini`` file that shows configuration used
-  Supports install/uninstall/starting/stopping of OpenStack components.
-  In various styles (daemonizing via `forking`_, `screen`_, `upstart`_)
-  Written in python so it matches the style of other OpenStack
   components.
-  Extensively documented distribution specifics
-  Packages and pip (with versions known to work!) dependencies
-  Any needed distribution specific actions (ie service names…)
-  See ``conf/distros``
-  Follows standard software development practices (for everyones
   sanity).
-  Functions, classes, objects and more (oh my!)
-  Still *readable* by someone with limited python knowledge.
-  The ability to be unit-tested!

Important!
==========

**Warning:** Be sure to carefully read ``stack`` and any other scripts
you execute before you run them, as they install software and may alter
your networking configuration. We strongly recommend that you run
``stack`` in a clean and disposable virtual machine when you are first
getting started.

.. _DEVSTACK: http://devstack.org/
.. _Beginners
guide: https://github.com/yahoo/Openstack-DevstackPy/wiki/Simple-Setup
.. _Examples: https://github.com/yahoo/Openstack-DevstackPy/wiki/Examples
.. _Bugs, hugs and
code: https://github.com/yahoo/Openstack-DevstackPy/wiki/Bugs,-Hugs
.. _Q+A: https://github.com/yahoo/Openstack-DevstackPy/wiki/Questions-and-answers
.. _Solved
problems/workarounds: https://github.com/yahoo/Openstack-DevstackPy/wiki/Problems-Solved
.. _Hacking: https://github.com/yahoo/Openstack-DevstackPy/blob/master/HACKING.md
.. _Adding your own
distro: https://github.com/yahoo/Openstack-DevstackPy/wiki/Adding-a-new-distro.
.. _Adding your own
persona: https://github.com/yahoo/Openstack-DevstackPy/wiki/Adding-a-new-persona.
.. _Design
details: https://github.com/yahoo/Openstack-DevstackPy/wiki/Advanced
.. _Known
issues: https://github.com/yahoo/Openstack-DevstackPy/wiki/Known-issues
.. _epel: http://fedoraproject.org/wiki/EPEL
.. _forking: http://users.telenet.be/bartl/classicperl/fork/all.html
.. _screen: http://www.manpagez.com/man/1/screen/
.. _upstart: http://upstart.ubuntu.com/

.. |DEVSTACKpy| image:: http://farm8.staticflickr.com/7188/6821923128_35e84f868f_t.jpg
