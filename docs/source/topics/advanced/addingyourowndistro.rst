==========
Adding your own distribution
==========


Your mission...
=============

So you have decided you want to venture into the bowels of DEVSTACKpy
and want to get support for your latest and greatest distribution. This
wiki will hopefully make that adventure simpler by listing out the key
places, files and configs that may have to be adjusted to get that to
work. This tape will self-destruct in 5 seconds. 1..2..3..4..5, boom!

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

By looking at the config folder ``distros`` you should exactly which
packages and pips and commands are needed for each component by looking
at a similar distribution. So you first task is to determine exactly
what versions are available for your distribution. If a version doesn’t
exist the you may need to resort to either using the `pypi`_ index or
having to package it yourself. If a version is to new, this is usually
ok (your mileage may vary) and if its to old then that might also not be
ok (your mileage may vary).

Try it
------

Now that you have provided a new `YAML`_ distro file you should be able
to run through the simple setup wiki and see if the install will pass.
If that does try starting and then seeing if everything has started up
correctly.

.. _pypi: http://pypi.python.org
.. _YAML: http://yaml.org/