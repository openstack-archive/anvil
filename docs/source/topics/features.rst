========
Features
========

-  Multi distribution support
-  A set of configuration files (in yaml format) that shows common/component/distribution configurations
-  Supports the following *actions* on the various of `OpenStack`_ components.
 #. **Installing**: downloading, installing dependencies (`pypi`_ and apt/yum packaging specifics), establishing the 
    needed configuration  files, symlinks, adjustments, tweaks (and so on...)
 #. **Starting**: starting of the components sub-programs with
    the needed configuration via the common `daemon`_ model (with a ``pid``, ``stderr`` and ``stdout`` file set)
 #. **Stopping**: stopping of the previously started components 
 #. **Uninstalling**: removing installed configuration, undoing of installed files/directories,
    and removing of packaging to get back to an initial 'clean' state
 #. **Testing**: running each components unit tests (and in the future performing a simple set of integration tests)
 #. **Packaging**: creating a basic set of packages for the desired distributions
 #. **Status**: checking the status of the running components sub-programs
-  Supports dry-run mode (to see what *would* happen)
-  Tracking of all actions taken by a component via tracking like files (mainly for uninstall, but useful for analysis)
-  Written in python so it matches the style of other `OpenStack`_ components.
-  Code decoupling (thus encouraging re-use by others)
 #. Components/actions are isolated as individual classes (and so on). This 
    decouples component installation from the action and decoupling of the 
    commands/packages/pips the component will use to install itself from the
    component...
 #. Supports installation *personas* that define what is to be installed, thus
    decoupling the 'what' from the 'how'.
-  Extensively documented distribution specifics (also decoupled)
 #. See the ``conf/distros`` directory for examples
-  Progress resuming so that when you install you can ``ctrl+c`` ``./smithy`` and resume later (where applicable).
-  Extensive logging (and debug mode)
 #. All commands ran are logged, all configuration files read/write...
-  Package/pip tracking
 #. Each components ``pip-requires`` and ``test-requires`` are mapped to (and checked against) the distribution package
    or a pip package which can provide that requirement. 
 #. This allows for installations to use the distributions native packages (when applicable)
    as well as provides a list of pips which should be packaged by that distribution before the given `OpenStack`_ release
    is stabilized.
 #. This also allows for releases anvil to track exactly how (and what packages and what mapping) is needed for a given
    anvil release tag (which will map to a given `OpenStack`_ release tag), thus freezing what is needed for that release.

.. _epel: http://fedoraproject.org/wiki/EPEL
.. _forking: http://users.telenet.be/bartl/classicperl/fork/all.html
.. _screen: http://www.manpagez.com/man/1/screen/
.. _upstart: http://upstart.ubuntu.com/
.. _OpenStack: http://openstack.org/
.. _pypi: http://pypi.python.org/pypi
.. _daemon: http://en.wikipedia.org/wiki/Daemon_(computing)
