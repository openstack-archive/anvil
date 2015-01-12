.. _getting-started:

===============
Getting started
===============

Made to be as simple as possible, but not too simple...

Prerequisites
=============

RTFM
----

Read the great documentation for developers/admins at

- http://docs.openstack.org/developer/
- http://docs.openstack.org/

This will vastly help you understand what the configurations and options do
when ANVIL configures them.

Linux
-----

One of the tested distributions.

- RHEL 6.2+
- CentOS 6.2+
- Oracle Enteprise Linux 6.2+

You can get CentOS 6.2+ (**64-bit** is preferred) from https://www.centos.org/

Installation
============

Pre-setup
---------

Since RHEL requires a `tty`_ to perform ``sudo`` commands we need
to disable this so ``sudo`` can run without a `tty`_. This seems needed
since nova and other components attempt to do ``sudo`` commands. This
isn’t possible in RHEL unless you disable this (since those
instances won’t have a `tty`_).

::

    $ sudo visudo

Then comment out line

::

    Default requiretty

Also disable selinux:

::

     $ sudo vi /etc/sysconfig/selinux

Change `SELINUX=enforcing` to `SELINUX=disabled` then reboot.

::

     $ sudo reboot

Create specifc user to isolate all the Anvil processes from root user

::

    $ sudo useradd <username>
    $ sudo passwd <username>

Set user as sudoer

::

    $ sudo visudo

Add `<username>     ALL=(ALL)       ALL`

Make all the rest of actions as <username> user

::

    $ sudo su - <username>

Get git!
--------

::

    $ sudo yum install git -y


Download
--------

We’ll grab the latest version of ANVIL via git:

::

    $ git clone git://github.com/stackforge/anvil.git
    $ cd anvil


Configuration
-------------

Any configuration to be updated should now be done.

Please edit the corresponding yaml files in ``conf/components/`` or
``conf/components/personas`` to fit your desired configuration of nova/glance
and the other OpenStack components.

.. note::

    You can use ``-p <conf/components/required_file.yaml>`` to specify a
    different persona.

To specify which versions of OpenStack components you want to install select
or edit an origins configuration file from ``<conf/origins/>``.

.. note::

    You can use ``-o <conf/origins/origins_file.yaml>`` to specify this
    different origins file.

Respository notes for those with RedHat subscriptions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To enable the needed repositories for various requirements please also run::

    sudo subscription-manager repos --enable rhel-6-server-optional-rpms

You can also include the `RDO`_ repositories (which has even more of the needed
requirements). This will ensure that anvil has to build less dependencies
overall.

* http://openstack.redhat.com/Repositories

Pre-installing
--------------

In order to ensure that anvil will have its correct dependencies you need to
first run the bootstrapping code that will setup said dependencies for your
operating system.

::

    sudo ./smithy --bootstrap

Preparing
---------

Now prepare *OpenStacks* components by running the following:

::

    ./smithy -a prepare

You should see a corresponding OpenStack repositories getting downloaded using
git, python setups occurring and configuration files being written as well as
source rpm packages being built and a repository setup from those
components [#verbose]_.

Building
--------

Now build *OpenStacks* components by running the following:

::

    sudo ./smithy -a build

You should see a corresponding OpenStack components and dependencies at this
stage being packaged into rpm files and two repositories being setup for
you [#verbose]_. One repository will be the dependencies that the OpenStack
components need to run and th other will be the OpenStack components
themselves.


Issues
======

Please report issues/bugs to https://launchpad.net/anvil. Much appreciated!

.. _FlatManager: http://docs.openstack.org/trunk/openstack-compute/admin/content/configuring-flat-networking.html
.. _euca2ools: http://open.eucalyptus.com/wiki/Euca2oolsGuide
.. _PID: http://en.wikipedia.org/wiki/Process_identifier
.. _tty: http://linux.die.net/man/4/tty
.. _apache: https://httpd.apache.org/
.. _RDO: http://openstack.redhat.com/Main_Page
.. [#verbose] If you desire more informational output add a ``-v`` or a ``-vv`` to the command.
