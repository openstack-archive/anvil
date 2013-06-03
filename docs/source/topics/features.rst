.. _features:


========
Features
========

-  A set of configuration files (in yaml format) that shows common/component/distribution configurations.
-  Supports the following *actions* on the various `OpenStack`_ components.

   * **Installing**:

     * Automatically downloading source from git and performing tag/branch checkouts.
     * Automatically verifying and translating ``test-requires`` and ``pip-requires`` files to known `pypi`_/rpm packages.
     * Automatically installing and building dependencies/packaging (`pypi`_ and rpm) specifics for you.
     * Automatically configuring the needed  files, symlinks, adjustments, tweaks.

   * **Starting**: starting of the components sub-programs with
     the needed configuration via the common `daemon`_ model

     * Also creates a ``pid``, ``stderr`` and ``stdout`` file set for debugging/examination.

   * **Stopping**: stopping of the previously started components
   * **Uninstalling**: getting you back to an initial 'clean' state

     * Removing installed configuration.
     * Undoing of installed files/directories.
     * Removing of packages installed.

   * **Testing**: running each components unit tests (and in the future performing a simple set of integration tests)
   * **Packaging**: creating a basic set of packages that matches the components selected
   
     - Supports automatic injection of dependencies, creation of change log from git history.
   
   * **Status**: checking the status of the running components sub-programs

-  Supports **dry-run** mode (to see what *would* happen).
-  Written in **python** so it matches the style of other `OpenStack`_ components.
-  **Code decoupling** (thus encouraging re-use by others)

   * Components/actions are isolated as individual classes...
   * Supports installation *personas* that define what is to be installed, thus
     decoupling the 'what' from the 'how'.

-  **Install/start/stop... resumption** so that when you install you can ``ctrl+c`` and resume later (where applicable).
-  Extensive **logging** (and debug mode)

   * All commands ran are logged, all configuration files read/write...

-  **Package tracking and building**

   * Anvil can create a single rpm of your installation, as well as build or include all needed dependencies so that
     the software that is installed can be installed repeatedly and reliably in the future.
   * This allows for installations to use the distributions native packages (when applicable)
     as well as provides a list of pips which should be packaged by that distribution before the given `OpenStack`_ release
     is stabilized.
   * This also allows for releases of anvil to track exactly how (and what packages and what mapping) is needed for a given
     release tag (which maps to a given `OpenStack`_ release tag), thus freezing what is needed for that release to a 
     known set.

.. _epel: http://fedoraproject.org/wiki/EPEL
.. _forking: http://users.telenet.be/bartl/classicperl/fork/all.html
.. _screen: http://www.manpagez.com/man/1/screen/
.. _upstart: http://upstart.ubuntu.com/
.. _OpenStack: http://openstack.org/
.. _pypi: http://pypi.python.org/pypi
.. _daemon: http://en.wikipedia.org/wiki/Daemon_(computing)
