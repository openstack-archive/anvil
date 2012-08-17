========
Features
========

-  Multi distribution installs via a single tool (TODO: fix for folsom)
-  A single ``anvil.ini`` file that shows common/component configuration
-  Supports the following *actions* on the various of OpenStack components.
 #. **Installing**: downloading, installing dependencies (`pypi`_ and distribution packaging specifics)
    and configuring component files and symlinks
 #. **Starting**: starting of the components sub-programs with
    the needed configuration via the common `daemon`_ model (with a ``pid``, ``stderr`` and ``stdout`` file set)
 #. **Stopping**: stopping of the previously started components 
 #. **Uninstalling**: removing installed configuration, undoing of installed files/directories,
    and removing of packaging to get back to an initial 'clean' state
 #. **Testing**: running each components unit tests (and in the future performing a simple set of integration tests)
 #. **Packaging**: creating a basic set of packages for the desired distributions
 #. **Status**: checking the status of the running components sub-programs
-  Supports dry-run mode (to see what *would* happen for each action)
-  Tracking of all actions taken by a component via tracking like files.
-  Written in python so it matches the style of other `OpenStack`_ components.
-  Code decoupling (thus encouraging re-use by others)
 #. Components/actions are isolated as individual classes (and so on). This 
    decouples component installation from the action and decoupling of the 
    commands/packages/pips the component will use to install itself from the
    component...
 #. Supports installation *personas* that define what is to be installed, thus
    decoupling the 'what' from the 'how'
-  Extensively documented distribution specifics
-  The ability to be unit-tested!
-  Progress resuming so that when you install you can ``ctrl+c`` ``./smithy`` and resume later (where applicable).
-  Extensive logging (and debug mode)

.. _epel: http://fedoraproject.org/wiki/EPEL
.. _forking: http://users.telenet.be/bartl/classicperl/fork/all.html
.. _screen: http://www.manpagez.com/man/1/screen/
.. _upstart: http://upstart.ubuntu.com/
.. _OpenStack: http://openstack.org/
.. _pypi: http://pypi.python.org/pypi
.. _daemon: http://en.wikipedia.org/wiki/Daemon_(computing)
