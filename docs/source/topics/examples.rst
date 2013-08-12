.. _examples:


========
Examples
========

Bootstrapping
-------------

This is needed to get ready for the rest of anvils stages by installing anvils
python dependencies so that anvil can correctly run using said dependencies.

::

     $ sudo ./smithy --bootstrap

**Terminal recording**: `<http://showterm.io/effa75ea631777a2e74a0/>`_

Preparing
---------

This stage does the download of the source repositories, analysis of dependencies,
download of missing dependencies and building of source repositories and missing
dependencies into source rpms.

::

     $ ./smithy -a prepare

**Terminal recording**: `<http://showterm.io/12c29e87094f128d945fa/>`_

Building
--------

This is the stage responsible for translating the previously prepared source rpms
into installable rpms (of the non-source type). The output of this phase is two
repositories, one with the dependencies and one with the rpms for the openstack
components themselves.

::

     $ sudo ./smithy -a build

**Terminal recording**: `<http://showterm.io/2fee38794dcf536ccd437/>`_

Installing
----------

This is the stage that is responsible for ensuring the needed rpms are still
available and installing them onto your system (using all the created dependencies
and repositories from the previous stages). It also configures the components
configuration files (paste for example) and sets up the needed databases and MQ
components (rabbit or qpid).

::

     $ sudo ./smithy -a install

**Terminal recording**: `<http://showterm.io/ed2611a6f9c086acfa8f8/>`_

Testing
-------

This acts as a single entrypoint to run the various components test suites, which
is typically a mixture of ``testr`` or ``nose``.

::

     $ sudo ./smithy -a test

**Note:** to ignore component test failures pass a ``-i`` to ``smithy``.

Starting
--------

This stage now starts the services for the individual components. At this stage,
since each component was packaged as an rpm we also nicely included a set of init.d
scripts for each component in its rpm; this starting support uses those init.d scripts
to start those components up. It also goes about running the needed post-start actions,
including downloading+installing an image for you, setting up keystone
configuration and making your nova network.

::

     $ sudo ./smithy -a start

**Terminal recording**: `<http://showterm.io/8ad5f96882e09a4d97ca3/>`_

Status
------

This stage uses the service control layer to show the status of all components.

::

     $ sudo ./smithy -a status

**Terminal recording**: `<http://showterm.io/d5f692b8cf8f7e6e8325f/>`_

Stopping
--------

This stage uses the service control layer to stop all components.

::

     $ sudo ./smithy -a stop

**Terminal recording**: `<http://showterm.io/a3a23838ebd476d93a6a1/>`_

Packaging
---------

To see the packages built (after prepare has finished). 

::

    $ ls /home/harlowja/openstack/deps/rpmbuild/SPECS/ | cat

.. literalinclude:: examples/spec_dir.txt
   :language: none
   :linenos:

::

    $ cat openstack-deps.spec

.. literalinclude:: examples/openstack-deps.txt
   :language: none
   :linenos:

::

    $ cat python-nova.spec 

.. literalinclude:: examples/nova-spec.txt
   :language: none
   :linenos:


Uninstalling
------------

This removes the packages that were installed (+ it does some extra cleanup of
some components dirty laundry that is sometimes left behind), restoring your
environment back to its pre-installation state.

::

     $ sudo ./smithy -a uninstall

**Terminal recording**: `<http://showterm.io/3e4d8892084e5f66ac18d/>`_

Purging
-------

This completly purges the anvil installation, uninstalling packages that were
installed, removing files and directories created (and any files there-in).
It is the single way to completely remove all traces of an anvil installation.

::

     $ sudo ./smithy -a purge

**Terminal recording**: `<http://showterm.io/e4fb03115ad3a224cafd5/>`_
