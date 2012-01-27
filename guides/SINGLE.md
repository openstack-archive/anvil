# Prerequisites (Linux & Network)

## Linux

One of the test linux distribtuions (ie RHEL 6.2 or Ubuntu 11.10 (Oneiric))

You can download the [Minimal CD](https://help.ubuntu.com/community/Installation/MinimalCD) 
for Oneiric (only 23MB) since DevStack v2 will install all the additional dependencies.

TODO: add a CentOS 6 link (?)

## Network Configuration

TODO: (need to get ken's input on this)

# Installation

## Horizon user

We need to add a user to install DevStack v2 so that horizon can run under apache.

For ubuntu:

    $ apt-get install sudo -y
    $ sudo adduser horizon
    $ sudo adduser horizon admin
    
## Download DevStack v2

We'll grab the latest version of DevStack v2 via git:

For ubuntu:

    $ sudo apt-get install git -y
    $ git clone git://github.com/yahoo/Openstack-Devstack2.git Devstack2
    $ cd Devstack2
    
## Adjust config

We need to adjust the configuration of DevStack v2 to reflect the above user.

Open *conf/stack.ini*

**Change section:**

    [horizon]
    
    # What user will apache be serving from
    #
    # Root will typically not work (so this is here to fail)
    # sudo adduser <username> then sudo adduser <username> admin will be what you want to set this up.
    # I typically use user "horizon"
    apache_user = ${APACHE_USER:-root}
    
    # This is the group of the previous user (adjust as needed)
    apache_group = ${APACHE_GROUP:-$(horizon:apache_user)}

**To:**

    [horizon]
    
    # What user will apache be serving from
    #
    # Root will typically not work (so this is here to fail)
    # sudo adduser <username> then sudo adduser <username> admin will be what you want to set this up.
    # I typically use user "horizon"
    apache_user = ${APACHE_USER:-horizon}
    
    # This is the group of the previous user (adjust as needed)
    apache_group = ${APACHE_GROUP:-$(horizon:apache_user)}

We need to adjust the configuration of DevStack v2 to reflect our above network configuration.

TODO: !!

## Activate install 

Now install DevStack v2 by running the following:

    sudo ./stack -a install -d $HOME/openstack

You should see a set of distro packages and/or pips being installed, python setups occuring and configuration
files being written as DevStack v2 figures out how to install your desired components.

# Run

Now that you have installed OpenStack you can now start OpenStack by running the following.

    sudo ./stack -a start -d $HOME/openstack

## Check horizon

Once that occurs you should be able to go to your hosts ip with a web browser and view horizon which can be logged in with
the user "admin" and the password you entered when prompted for "Enter a password to use for horizon and keystone".
If you let the system out generate one for you you will need to check the final output of the above install
and pick up the password that was generated which should be displayed at key *passwords/horizon_keystone_admin*.

If you see a login page and can access horizon then:

*Congratulations. You did it!*

Otherwise you may have to look at the output of what was started. To accomplish this you may have to log at the
stderr and stout that is being generated from the running OpenStack process (by default they are forked as daemons).
For this information check the output of the start command for a line like "Check * for traces of what happened".
This is usually a good starting point, to check out those files contents and then lookup the files that contain
the applications [PID](http://en.wikipedia.org/wiki/Process_identifier) and stderr and stdout.

# Stopping

Once you have started OpenStack you can stop it by running the following:

    sudo ./stack -a stop -d $HOME/openstack

You should see a set of stop actions happening and stderr & stdout & pid files being removed. This ensures
the above a daemon that was started is now killed. A good way to check if it killed everything correctly is to
run the following.

    sudo ps -elf | grep python
    sudo ps -elf | grep apache

There should be no entries like *nova*, *glance*, *apache*. If there are then the stop may have not occured correctly.

# Uninstalling

Once you have stopped (if you have started it) OpenStack you can uninstall it by running the following:

    sudo ./stack -a uninstall -d $HOME/openstack

You should see a set of packages, configuration and directories, being removed. On completion
the directory specified at $HOME/openstack should no longer exist. 
