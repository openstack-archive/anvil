==========
Adding your own persona
==========


Your mission...
=============

So you have decided you want to venture into the bowels of DEVSTACKpy
and want to alter what is installed/started/stopped, the order of what
is installed/started/stopped, what subsystems are activated (or the
component options). This wiki will hopefully make that adventure simpler
by listing out the key places, files and configs that may have to be
adjusted to get that to work. This tape will self-destruct in 5 seconds.
1..2..3..4..5, boom!

Steps
=====

Snapshot
--------

One of the most useful things to do will be to get a virtual machine
with your distribution and setup a stable state. Create a snapshot of
that stable state just in-case you *bork* your machine later on.

Logging
-------

Now turn ensure you run ``DEBUG/VERBOSE`` logging using ``-vv``. This
will be useful to see exactly what actions and commands are being ran
instead of the default ``INFO`` level logging which is just meant for
simple informational messages about the underlying actions which are
occurring.

Configs
-------

By looking at the config folder ``personas`` you should a file called
``devstack.sh.yaml``. This file contains the component order of
installation (ie the ``db`` before ``keystone``), a nice useful
description of the persona and subsystems for the previously specified
components and any options these components may have. So you first task
is to determine exactly what of these you wish to change (if any). Note
that changing the component order may not always work (ie typically
starting components are dependent, ie the message queue needs to be
started before nova). To add in new components check the ``distros``
folder to determine exactly what that component is named (typically this
is common) and alter the persona file as desired. To alter the
``subsystems`` or ``options`` section you will have to jump in the code
and check for what these values could be (TODO make that better).

Try it
------

Now that you have provided a new `YAML`_ persona file you should be able
to run the ``stack`` program with that persona through the ``-p``
option.

.. _YAML: http://yaml.org/