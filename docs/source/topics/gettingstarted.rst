.. _getting-started:

===============
Getting Started
===============


Simple setup!
=============

Made to be as simple as possible, but not to simple.

Prerequisites
=============

Linux
-----

One of the tested Linux distributions (RHEL 6.2, Ubuntu 11.10, Fedora
16)

You can get Ubuntu 11.10 (**64-bit** is preferred) from
http://releases.ubuntu.com/11.10/

You can get RHEL 6.2 (**64-bit** is preferred) from
http://rhn.redhat.com/.

You can get Fedora 16 (**64-bit** is preferred) from
https://fedoraproject.org/get-fedora, so don’t worry if you do not have
a RHN subscription.

Networking
----------

**Important!**
--------------

Since networking can affect how your cloud runs please check out this
link:

http://docs.openstack.org/diablo/openstack-compute/admin/content/configuring-networking-on-the-compute-node.html

Check out the root article and the sub-chapters there to understand more
of what these settings mean.

**This is typically one of the hardest aspects of *OpenStack* to
configure and get right!**

--------------

DEVSTACKpy will configure the network in a identical manner to version
*1.0*. This means that the default network manager will be the
*FlatDHCPManager*. The following settings are relevant in configuring
your network.

::

     flat_network_bridge = ${FLAT_NETWORK_BRIDGE:-br100}
     flat_interface = ${FLAT_INTERFACE:-eth0}
     public_interface = ${PUBLIC_INTERFACE:-eth0}

The above settings will affect exactly which network interface is used
as the *source* interface which will be used as a network *bridge*.

::

    fixed_range = ${NOVA_FIXED_RANGE:-10.0.0.0/24}
    fixed_network_size = ${NOVA_FIXED_NETWORK_SIZE:-256} 
    floating_range = ${FLOATING_RANGE:-172.24.4.224/28}
    test_floating_pool = ${TEST_FLOATING_POOL:-test}
    test_floating_range = ${TEST_FLOATING_RANGE:-192.168.253.0/29}

The above settings will determine exactly how nova when running assigns
IP addresses. By default a single network is created using
*fixed\_range* with a network size specified by *fixed\_network\_size*.
Note the size here is *256* which is the number of addresses in the
*10.0.0.0/24* subnet (*32 - 24* bits is 8 bits or 256 addresses). The
floating pool is similar to fixed addresses (**TODO** describe this
more).

Installation
============

Pre-setup
---------

Since RHEL/Fedora requires a `tty`_ to perform ``sudo`` commands we need
to disable this so ``sudo`` can run without a `tty`_. This seems needed
since nova and other components attempt to do ``sudo`` commands. This
isn’t possible in RHEL/Fedora unless you disable this (since those
instances won’t have a `tty`_ ).

**For RHEL and Fedora 16:**

::

    $ sudo visudo 

Then comment out line:

::

    Default requiretty

Also disable selinux:

::

     $ sudo vi /etc/sysconfig/selinux

Change *SELINUX=enforcing* to *SELINUX=disabled* then it seems you need
to reboot.

::

     $ sudo reboot

**For Ubuntu:**

You are off the hook.

Users
-----

We need to add a admin user so that horizon can run under `apache`_.

**For Ubuntu:**

::

    $ apt-get install sudo -y
    $ sudo adduser horizon
    $ sudo adduser horizon admin

**For RHEL/Fedora 16:**

You are off the hook as long as your user has ``sudo`` access.

Download
--------

We’ll grab the latest version of DEVSTACKpy via git:

::

    $ git clone git://github.com/yahoo/Openstack-DevstackPy.git DevstackPy

Now setup the prerequisites needed to run DEVSTACKpy:

::

    $ cd DevstackPy && sudo ./prepare.sh

Configuration
-------------

Apache configuration
~~~~~~~~~~~~~~~~~~~~

We need to adjust the configuration of DEVSTACKpy to reflect the above
user (``iff you created a user``).

Open ``conf/stack.ini``

**Change section:**

::

    [horizon]

    # What user will apache be serving from.
    #
    # Root will typically not work (for apache on most distros)
    # sudo adduser <username> then sudo adduser <username> admin will be what you want to set this up (in ubuntu)
    # I typically use user "horizon" for ubuntu and the runtime user (who will have sudo access) for RHEL.
    #
    # NOTE: If blank the currently executing user will be used.
    apache_user = ${APACHE_USER:-}

**To:**

::

    [horizon]

    # What user will apache be serving from.
    #
    # Root will typically not work (for apache on most distros)
    # sudo adduser <username> then sudo adduser <username> admin will be what you want to set this up (in ubuntu)
    # I typically use user "horizon" for ubuntu and the runtime user (who will have sudo access) for RHEL.
    #
    # NOTE: If blank the currently executing user will be used.
    apache_user = ${APACHE_USER:-horizon}

Network configuration
~~~~~~~~~~~~~~~~~~~~~

We need to adjust the configuration of DEVSTACKpy to reflect our above
network configuration.

Please reference
http://docs.openstack.org/diablo/openstack-compute/admin/content/configuring-networking-on-the-compute-node.html

If you need to adjust those variables the matching conf

TRUNCATED! Please download pandoc if you want to convert large files.

.. _tty: http://linux.die.net/man/4/tty
.. _apache: https://httpd.apache.org/
