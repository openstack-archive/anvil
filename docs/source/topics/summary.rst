.. _summary:

===============
Summary
===============

Anvil is a forging tool to help build OpenStack components and their
dependencies into a complete package-oriented system.

It automates the git checkouts of the OpenStack components, analyzes & builds
their dependencies and the components themselves into packages.

It allows a developer to setup an environment using the automatically created
packages (and dependencies, ex. ``RPMs``) with the help of anvil configuring
the components to work correctly for the developer's needs.

The distinguishing part from devstack_ (besides being written in Python and not
shell), is that after building those packages (currently ``RPMs``) the same
packages can be used later (or at the same time) to  actually deploy at a
larger scale using tools such as `chef`_, `salt`_, or `puppet`_ (to name a few).

--------
Features
--------

Configurations
--------------

A set of configuration files (in `yaml`_ format) that is used for
common, component, distribution, code origins configuration...

All the `yaml`_ configuration files could be found in:

* ``conf/templates/keystone/``
* ``conf/components/``
* ``conf/distros/``
* ``conf/origins/``
* subdirectories of ``conf/personas/``


Packaging
----------

* Automatically downloading source from git and performing tag/branch checkouts.
* Automatically verifying and translating requirement files to
  known `pypi`_/`rpm`_ packages.
* Automatically installing and building missing dependencies (`pypi`_
  and `rpm`_) for you.
* Automatically configuring the needed files, symlinks, adjustments, and
  any patches.

Pythonic
--------

Written in **python** so it matches the style of other `OpenStack`_ components.

Code decoupling
---------------

* Components & actions are isolated as individual classes.
* Supports installation personas that define what is to be installed, thus
  decoupling the 'what' from the 'how'.

.. note::

    This encouraging re-use by others...

Extensive logging
-----------------

* All commands executed are logged in standard output, all configuration files
  read/written (and so on).

.. note::

    Debug mode can be activated with ``-v`` option...

Package tracking and building
-----------------------------

* Creation of a single ``RPM`` set for your installation.

  * This *freezes* what is needed for that release to a known set of
    packages and dependencies.

* Automatically building and/or including all needed dependencies.
* Includes your distributions *existing* native/pre-built packages (when
  and where applicable).

  * For example uncommenting the following in the `bootstrap`_ file will allow
    anvil to find dependencies in the `epel`_ repository.

.. _bootstrap: http://github.com/stackforge/anvil/blob/master/tools/bootstrap/CommonRedHat#L7
.. _OpenStack: http://openstack.org/
.. _chef: http://www.opscode.com/chef/
.. _daemon: http://en.wikipedia.org/wiki/Daemon_(computing)
.. _devstack: http://www.devstack.org/
.. _epel: http://fedoraproject.org/wiki/EPEL
.. _puppet: http://puppetlabs.com/
.. _pypi: http://pypi.python.org/pypi
.. _rpm: http://www.rpm.org/
.. _salt: http://saltstack.com/
.. _sysvinit: http://en.wikipedia.org/wiki/Init
.. _yaml: http://www.yaml.org/
