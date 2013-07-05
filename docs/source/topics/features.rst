.. _features:


========
Features
========

Configurations
--------------

A set of configuration files (in yaml format) that shows common/component/distribution configurations.
All the yaml configuration files could be found in:

* conf/templates/keystone/
* conf/components/
* conf/distros/
* subdirectories of conf/personas/


Installing
----------

* Automatically downloading source from git and performing tag/branch checkouts.
* Automatically verifying and translating requirement files to known `pypi`_/rpm packages.
* Automatically installing and building missing dependencies (`pypi`_ and rpm) for you.
* Automatically configuring the needed files, symlinks, adjustments, and any patches.

Testing
-------

Automatically running each component unit tests.

Starting
--------

Starting of the components sub-programs with the needed configuration via the common `daemon`_ model.

* Also creates a ``pid``, ``stderr`` and ``stdout`` file set for debugging/examination.
* Trace files could be found in $HOME/openstack/<component>/traces/

Stopping
--------

Stopping of the previously started components.

Uninstalling
------------

Getting you back to an initial 'clean' state:

* Removing installed configuration.
* Undoing of installed files/directories.
* Removing of packages installed.

Packaging
---------

* Ceating a basic set of packages that matches the components selected.
* Supports automatic injection of dependencies and creation of a ``changelog`` from git history.

Status
------

* Checking the status of the running components sub-programs

Dry run
-------

``dry_run`` satisfied with any action it turns verbose and all modifying the outside world calls (running external commands, kill, mkdir ......) are not executing.

Pythonic
--------

Written in **python** so it matches the style of other `OpenStack`_ components.

Code decoupling
---------------

(thus encouraging re-use by others)

* Components & actions are isolated as individual classes.
* Supports installation personas that define what is to be installed, thus decoupling the 'what' from the 'how'.

Resumption
----------

Install/start/stop resumption so that when you install you can ``ctrl+c`` and resume later (where applicable).

Extensive logging
-----------------

* All commands executed are logged in standard output, all configuration files read/written (and so on).
* Debug mode could be activate with ``-v`` option

Package tracking and building
-----------------------------


* Creation of a single rpm of your installation. This freezes what is needed for that release to a known set of packages and dependencies.
* Automatically building and/or including all needed dependencies.
* Includes application of your distributions native packages (when applicable).

.. _OpenStack: http://openstack.org/
.. _daemon: http://en.wikipedia.org/wiki/Daemon_(computing)
.. _pypi: http://pypi.python.org/pypi
