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

http://docs.openstack.org/trunk/openstack-compute/admin/content/configuring-networking-on-the-compute-node.html

Check out the root article and the sub-chapters there to understand more
of what these settings mean.

**This is typically one of the hardest aspects of *OpenStack* to
configure and get right!**

--------------

ANVIL will configure the network in a identical manner to version
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

Also to avoid qemu errors please follow the solution @ https://bugs.launchpad.net/anvil/+bug/985786
which will ensure that the ``qemu`` user can write to your instances directory. If needed edit ``anvil.ini``
and also adjust the ``instances_path`` option (under the ``nova`` section).

This can be typically solved by running the following (and then updating ``anvil.ini``):

::

    $ sudo mkdir -pv /home/openstack
    $ sudo chmod -R a+rwx /home/openstack


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

Get git!
--------

**For Ubuntu:**

::

    $ sudo apt-get install git -y

**For RHEL/Fedora 16:**

::

    $ sudo yum install git -y


Download
--------

We’ll grab the latest version of ANVIL via git:

::

    $ git clone git://github.com/yahoo/Openstack-Anvil.git anvil

Now setup the prerequisites needed to run (select the appropriate shell script for your distro):

::

    $ cd anvil/warmups && sudo ./$DISTRO.sh

Configuration
-------------

Apache configuration
~~~~~~~~~~~~~~~~~~~~

We need to adjust the configuration of ANVIL to reflect the above
user (``iff you created a user``).

Open ``conf/anvil.ini``

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

We need to adjust the configuration of ANVIL to reflect our above network configuration.

Please reference:

http://docs.openstack.org/diablo/openstack-compute/admin/content/configuring-networking-on-the-compute-node.html

If you need to adjust those variables the matching config variables in ``anvil.ini`` are:

::

    # Network settings
    # Very useful to read over:
    # http://docs.openstack.org/cactus/openstack-compute/admin/content/configuring-networking-on-the-compute-node.html
    fixed_range = ${NOVA_FIXED_RANGE:-10.0.0.0/24}
    fixed_network_size = ${NOVA_FIXED_NETWORK_SIZE:-256}
    network_manager = ${NET_MAN:-FlatDHCPManager}
    public_interface = ${PUBLIC_INTERFACE:-eth0}

    # DHCP Warning: If your flat interface device uses DHCP, there will be a hiccup while the network 
    # is moved from the flat interface to the flat network bridge. This will happen when you launch 
    # your first instance. Upon launch you will lose all connectivity to the node, and the vm launch will probably fail.
    #
    # If you are running on a single node and don't need to access the VMs from devices other than 
    # that node, you can set the flat interface to the same value as FLAT_NETWORK_BRIDGE. This will stop the network hiccup from occurring.
    flat_interface = ${FLAT_INTERFACE:-eth0}
    vlan_interface = ${VLAN_INTERFACE:-$(nova:public_interface)}
    flat_network_bridge = ${FLAT_NETWORK_BRIDGE:-br100}

    # Test floating pool and range are used for testing. 
    # They are defined here until the admin APIs can replace nova-manage
    floating_range = ${FLOATING_RANGE:-172.24.4.224/28}
    test_floating_pool = ${TEST_FLOATING_POOL:-test}
    test_floating_range = ${TEST_FLOATING_RANGE:-192.168.253.0/29}


If you are using a ``FlatManager`` and RH/Fedora then you might want read and follow:

http://www.techotopia.com/index.php/Creating_an_RHEL_5_KVM_Networked_Bridge_Interface
    
Installing
----------

Now install *OpenStacks* components by running the following:

::

    sudo ./smithy -a install -d ~/openstack

You should see a set of distribution packages and/or pips being
installed, python setups occurring and configuration files being written
as ANVIL figures out how to install your desired components (if you
desire more informational output add a ``-v`` or a ``-vv`` to that
command).

Starting
--------

Now that you have installed *OpenStack* you can now start your
*OpenStack* components by running the following.

::

    sudo ./smithy -a start -d ~/openstack

If you desire more informational output add a ``-v`` or a ``-vv`` to
that command.

Check horizon
~~~~~~~~~~~~~

Once that occurs you should be able to go to your hosts ip with a web
browser and view horizon which can be logged in with the user ``admin``
and the password you entered when prompted for
``Enter a password to use for horizon and keystone``. If you let the
system auto-generate one for you you will need to check the final output
of the above install and pick up the password that was generated which
should be displayed at key ``passwords/horizon_keystone_admin``. You can
also later find this authentication information in the generated
``core.rc`` file.

If you see a login page and can access horizon then:

``Congratulations. You did it!``

Command line tools
~~~~~~~~~~~~~~~~~~

In your ANVIL directory:

::

    source core.rc

This should set up the environment variables you need to run OpenStack
CLI tools:

::

    nova <command> [options] [args]
    nova-manage <command> [options] [args]
    keystone <command> [options] [args]
    glance <command> [options] [args]
    ....

If you desire to use eucalyptus tools (ie `euca2ools`_) which use the
EC2 apis run the following to get your EC2 certs:

::

    euca.sh $OS_USERNAME $OS_TENANT_NAME

It broke?
~~~~~~~~~

*Otherwise* you may have to look at the output of what was started. To
accomplish this you may have to log at the ``stderr`` and ``stdout``
that is being generated from the running *OpenStack* process (by default
they are forked as daemons). For this information check the output of
the start command for a line like
``Check * for traces of what happened``. This is usually a good starting
point, to check out those files contents and then look up the files that
contain the applications `PID`_ and ``stderr`` and ``stdout``.

If the install section had warning messages or exceptions were thrown
there, that may also be the problem. Sometimes running the uninstall
section below will clean this up, your mileage may vary though.

Another tip is to edit run with more verbose logging by running with the
following ``-v`` option or the ``-vv`` option. This may give you more
insights by showing you what was executed/installed/configured
(uninstall & start by installing again to get the additional logging
output).

Stopping
--------

Once you have started *OpenStack* services you can stop them by running
the following:

::

    sudo ./smithy -a stop -d ~/openstack

You should see a set of stop actions happening and ``stderr`` and
``stdout`` and ``pid`` files being removed (if you desire more
informational output add a ``-v`` or a ``-vv`` to that command). This
ensures the above a daemon that was started is now killed. A good way to
check if it killed everything correctly is to run the following.

::

    sudo ps -elf | grep python
    sudo ps -elf | grep apache

There should be no entries like ``nova``, ``glance``, ``apache``,
``httpd``. If there are then the stop may have not occurred correctly.
If this is the case run again with a ``-v`` or a ``-vv`` or check the
``stderr``, ``stdout``, ``pid`` files for any useful information on what
is happening.

Uninstalling
------------

Once you have stopped (if you have started it) *OpenStack* services you
can uninstall them by running the following:

::

    sudo ./smithy -a uninstall -d ~/openstack

You should see a set of packages, configuration and directories, being
removed (if you desire more informational output add a ``-v`` or a
``-vv`` to that command). On completion the directory specified at
~/openstack be empty.

Issues
======

Please report issues/bugs to https://launchpad.net/anvil. Much appreciated!

.. _euca2ools: http://open.eucalyptus.com/wiki/Euca2oolsGuide
.. _PID: http://en.wikipedia.org/wiki/Process_identifier
.. _tty: http://linux.die.net/man/4/tty
.. _apache: https://httpd.apache.org/
