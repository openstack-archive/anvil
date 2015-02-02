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
