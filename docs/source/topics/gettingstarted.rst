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

One of the tested Linux distributions (RHEL 6.2+ until further updated)

You can get RHEL 6.2+ (**64-bit** is preferred) from http://rhn.redhat.com/.

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

Since RHEL requires a `tty`_ to perform ``sudo`` commands we need
to disable this so ``sudo`` can run without a `tty`_. This seems needed
since nova and other components attempt to do ``sudo`` commands. This
isn’t possible in RHEL unless you disable this (since those
instances won’t have a `tty`_ ).

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
which will ensure that the ``qemu`` user can write to your instances directory. If needed edit ``conf/components/nova.yaml``
and also adjust the ``instances_path`` option.

This can be typically solved by running the following (and then updating the ``instances_path`` option)

::

    $ sudo mkdir -pv /home/openstack
    $ sudo chmod -R a+rwx /home/openstack



Get git!
--------

::

    $ sudo yum install git -y


Download
--------

We’ll grab the latest version of ANVIL via git:

::

    $ git clone git://github.com/yahoo/Openstack-Anvil.git anvil

Configuration
-------------


Network configuration
~~~~~~~~~~~~~~~~~~~~~

We need to adjust the configuration of ANVIL to reflect our above network configuration.

Please reference:

http://docs.openstack.org/diablo/openstack-compute/admin/content/configuring-networking-on-the-compute-node.html

If you need to adjust those variables the matching config variables in ``conf/components/nova.yaml`` are:

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

    sudo ./smithy -a install

You should see a set of distribution packages and/or pips being
installed, python setups occurring and configuration files being written
as ANVIL figures out how to install your desired components (if you
desire more informational output add a ``-v`` or a ``-vv`` to that
command).

Testing
----------

Now (if you choose) you can run each *OpenStack* components unit tests by running the following:

::

    sudo ./smithy -a test

You should see a set of unit tests being ran (ideally with zero failures).

Starting
--------

Now that you have installed *OpenStack* you can now start your
*OpenStack* components by running the following.

::

    sudo ./smithy -a start

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
``passwords.yaml`` file.

If you see a login page and can access horizon then:

``Congratulations. You did it!``

Command line tools
~~~~~~~~~~~~~~~~~~

In your ANVIL directory:

::

    source install.rc

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

    ./euca.sh $OS_USERNAME $OS_TENANT_NAME

It broke?
~~~~~~~~~

First run the following to check the status of each component.

::

    sudo ./smithy -a status

If you do not see all green status then you should run the following and see
if any of the ``stderr`` and ``stdout`` files will give you more information
about what is occuring

::

    sudo ./smithy -a status --show
    
This will dump out those files (truncated to not be to verbose) so that anything
peculaliar can be seen. If nothing can be then go to the installation directory (typically ``~/openstack``)
and check the ``traces`` directory of each component and check if anything looks fishy.

Stopping
--------

Once you have started *OpenStack* services you can stop them by running
the following:

::

    sudo ./smithy -a stop

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

    sudo ./smithy -a uninstall

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
