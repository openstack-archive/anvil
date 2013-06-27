.. _examples:


========
Examples
========

Pre-installing
--------------

See [Getting started! pre-setup] [gs] section to make the right preparation.

Bootstrapping
-------------

::

     $ sudo ./smithy --bootstrap


.. literalinclude:: examples/bootstrap.txt
   :language: none
   :linenos:


Preparing
---------

::

     $ sudo ./smithy -a prepare


.. literalinclude:: examples/prepare.txt
   :language: none
   :linenos:


Building
--------

::

     $ sudo ./smithy -a build


.. literalinclude:: examples/build.txt
   :language: none
   :linenos:

Installing
----------

::

     $ sudo ./smithy -a install


.. literalinclude:: examples/install.txt
   :language: none
   :linenos:


Testing
-------

::

     $ sudo ./smithy -a test


.. literalinclude:: examples/testing.txt
   :language: none
   :linenos:


Starting
--------

::

     $ sudo ./smithy -a start


.. literalinclude:: examples/starting.txt
   :language: none
   :linenos:


Status
------

::

     $ sudo ./smithy -a status


.. literalinclude:: examples/status.txt
   :language: none
   :linenos:


Stopping
--------

::

     $ sudo ./smithy -a stop


.. literalinclude:: examples/stopping.txt
   :language: none
   :linenos:


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

::

     $ sudo ./smithy -a uninstall


.. literalinclude:: examples/uninstall.txt
   :language: none
   :linenos:


[gs]: /en/latest/topics/gettingstarted.html#pre-setup
