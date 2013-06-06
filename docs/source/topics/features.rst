.. _features:


========
Features
========

-  A set of configuration files (in yaml format) that shows common/component/distribution configurations.
-  Supports the following *actions* on the various `OpenStack`_ components.

   * **Installing**:

     * Automatically downloading source from git and performing tag/branch checkouts.
     * Automatically verifying and translating requirement files to known `pypi`_/rpm packages.
     * Automatically installing and building missing dependencies (`pypi`_ and rpm) for you.
     * Automatically configuring the needed files, symlinks, adjustments, and any patches.

   * **Starting**: starting of the components sub-programs with
     the needed configuration via the common `daemon`_ model.

     * Also creates a ``pid``, ``stderr`` and ``stdout`` file set for debugging/examination.

   * **Stopping**: stopping of the previously started components.
   * **Uninstalling**: getting you back to an initial 'clean' state.

     * Removing installed configuration.
     * Undoing of installed files/directories.
     * Removing of packages installed.

   * **Testing**: automatically running each components unit tests.
   * **Packaging**: creating a basic set of packages that matches the components selected.
   
     - Supports automatic injection of dependencies and creation of a ``changelog`` from git history.
   
   * **Status**: checking the status of the running components sub-programs

-  Supports **dry-run** mode (to see what *would* happen).
-  Written in **python** so it matches the style of other `OpenStack`_ components.
-  **Code decoupling** (thus encouraging re-use by others)

   * Components & actions are isolated as individual classes.
   * Supports installation *personas* that define what is to be installed, thus
     decoupling the 'what' from the 'how'.

-  **Install/start/stop... resumption** so that when you install you can ``ctrl+c`` and resume later (where applicable).
-  Extensive **logging** (and debug mode)

   * All commands executed are logged, all configuration files read/written (and so on).

-  **Package tracking and building**

   * Creation of a single rpm of your installation. 

     * This freezes what is needed
       for that release to a known set of packages and dependencies.

   * Automatically building and/or including all needed dependencies.

     * Includes application of your distributions native packages (when applicable).

.. _epel: http://fedoraproject.org/wiki/EPEL
.. _forking: http://users.telenet.be/bartl/classicperl/fork/all.html
.. _screen: http://www.manpagez.com/man/1/screen/
.. _upstart: http://upstart.ubuntu.com/
.. _OpenStack: http://openstack.org/
.. _pypi: http://pypi.python.org/pypi
.. _daemon: http://en.wikipedia.org/wiki/Daemon_(computing)
