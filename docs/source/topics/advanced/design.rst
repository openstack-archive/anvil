========
Design
========

How it works
------------

DEVSTACKpy is based along the following system design
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Having shared components/actions be shared (using object oriented
   practices)
-  Having specific actions be isolated to its component (and easily
   readable)
-  Being simple enough to read yet following standard python software
   development practices and patterns

Directory structure is the following
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Parent classes located in *devstack/component.py*, it contains the
   root install/uninstall/start/stop classes
-  Subclasses in *devstack/components/*, it contains the individual
   install classes for each openstack component
-  Running modes implementations in *devstack/runners/* (ie fork,
   screen, upstart)
-  Packaging implementations in *devstack/packaging/*
-  Image uploading/registry/management (for glance) in *devstack/image/*
-  Shared classes and utils in *devstack/*
-  Main entry point/s in *devstack/progs/*
-  Other various tools in *tools/*
-  Configuration in *conf/* (see below)

Example
~~~~~~~

Install object model
^^^^^^^^^^^^^^^^^^^^

Here is the **install** components (default set only) class hierarchy:

.. figure:: http://farm8.staticflickr.com/7043/6894250521_d882b770d1_o.png
   :align: center

Classes
'''''''

From this example the root classes job are:

-  Python install component
-  Ensures *pips* are installed (child classes specify which pips)
-  Ensures python directories (ie *setup.py*) are setup (child classes
   specify which directories)
-  Package install component
-  Installs packages that are required for install (child classes
   specify which packages)
-  Sets up and performs parameter replacement on config files (child
   classes specify which config files)
-  Sets up symlinks to config or other files (child classes specify
   these symlinks)
-  Tracks what was setup so that it can be removed/uninstalled
-  Component base (used by **all** install/uninstall/start/stop
   component classes)
-  Holds configuration object, component name, packaging and other
   shared members…
-  Allows for overriding of dependency function and pre-run verification

Functions
'''''''''

For a install class the following functions are activated (in the
following order by *devstack/progs/actions.py*):

::

      download()

    Performs the main git download (or other download type) to the
    application target directory.

::

      configure()

    Configures the components files (symlinks, configuration and logging
    files…)

::

      pre_install()

    Child class specific function that can be used to do anything before
    an install (ie set a ubuntu mysql pre-install root password)

::

      install()

    Installs distribution packages, python packages (*pip*), sets up
    python directories (ie *python setup.py develop*) and any other
    child class specific actions.

::

      post_install()

    Child class specific function that can be used to do anything after
    an install (ie run *nova-manage db sync*)

Other object models
^^^^^^^^^^^^^^^^^^^

-  `Start object model (for default set only)`_
-  `Stop object model (for default set only)`_
-  `Uninstall object model (for default set only)`_

Configuring
-----------

For those of you that are brave enough to change *stack* here are some
starting points.

conf/stack.ini
~~~~~~~~~~~~~~

Check out *conf/stack.ini* for various configuration settings applied
(branches, git repositories…). Check out the header of that file for how
the customized configuration values are parsed and what they may result
in.

conf/distros
~~~~~~~~~~~~

Check out *conf/distros* for the `YAML`_ files that describe
pkgs/cmds/pips for various distributions which are required by the
different OpenStack components to run correctly. The versions and pip
names listed for each distribution should be the correct version that is
known to work with a given OpenStack release.

conf/templates/
~~~~~~~~~~~~~~~

Check out *conf/templates/* for various component specific settings and
files. All of these files are *templates* with sections or text that
needs to be filled in by the ``stack`` script to become a *complete*
file.

These files may have strings of the format ``%NAME%`` where ``NAME``
will most often be adjusted to a real value by the *stack* script.

An example where this is useful is say for the following line:

::

       admin_token = %SERVICE_TOKEN% 

Since the script will either prompt for this value (or generate it for
you) we can not have this statically set in a configuration file.

.. _Start object model (for default set only): http://farm8.staticflickr.com/7046/6894981327_a583bcb4fc_o.png
.. _Stop object model (for default set only): http://farm8.staticflickr.com/7059/6894981341_e6d4901b20_o.png
.. _Uninstall object model (for default set only): http://farm8.staticflickr.com/7177/6894981357_fef65b28d3_o.png
.. _YAML: http://yaml.org/