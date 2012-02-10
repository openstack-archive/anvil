*DevstackPy* is a set of **python** scripts and utilities to quickly deploy an OpenStack cloud.

# Goals

* To quickly build dev OpenStack environments in a clean environment (as well as start, stop, and uninstall those environments) with as little baggage as possible.
* To describe working configurations of OpenStack.
    * Which code branches work together? 
    * What do config files look like for those branches? 
    * What packages are needed for installation for a given distribution?
* To make it easier for developers to dive into OpenStack so that they can productively contribute without having to understand every part of the system at once.
* To make it easy to prototype cross-project features.

**IMPORTANT:** Be sure to carefully read *stack* and any other scripts you execute before you run them, as they install software and may alter your networking configuration.  We strongly recommend that you run stack in a clean and disposable vm when you are first getting started. (*TODO* dry-run mode would be great!).

# Help

In order to determine what *stack* can do for you run the following.

    ./stack --help
 
This will typically produce:
    
    Usage: stack [options]
    
    Options:
      --version             show program's version number and exit
      -h, --help            show this help message and exit
      -c COMPONENT, --component=COMPONENT
                            openstack component: [db, glance, horizon, keystone,
                            keystone-client, melange, melange-client, nova, nova-
                            client, novnc, quantum, quantum-client, rabbit, swift,
                            swift-keystone]
    
      Install/uninstall/start/stop options:
        -a ACTION, --action=ACTION
                            required action to perform: [install, start, stop,
                            uninstall]
        -d DIR, --directory=DIR
                            empty root DIR for install or DIR with existing
                            components for start/stop/uninstall
        -i, --ignore-deps   ignore dependencies when performing ACTION
        -e, --ensure-deps   ensure dependencies when performing ACTION (default:
                            True)
        -r COMPONENT, --ref-component=COMPONENT
                            component which will not have ACTION applied but will be
                            referenced as if it was (ACTION dependent)
        -k, --keep-packages
                            uninstall will keep any installed packages on the system
    
      Uninstall/stop options:
        -n, --no-force      stop the continuation of ACTION if basic errors occur
                            (default: False)

# Stack prerequisites

* linux (tested on ubuntu 11.10 and rhel 6.2)
* python 2.6 or 2.7 (not tested with python 3.0)

For ubuntu 11.10:

    $ sudo apt-get install git python-pip python-dev gcc -y
    $ sudo easy_install netifaces termcolor pep8 pylint
    $ git clone git://github.com/yahoo/Openstack-DevstackPy.git DevstackPy
    $ cd DevstackPy

For rhel 6.2:

    $ wget http://download.fedoraproject.org/pub/epel/6/i386/epel-release-6-5.noarch.rpm
    $ sudo yum install -y epel-release-6-5.noarch.rpm
    $ sudo yum install -y python-pip gcc python-netifaces git
    $ sudo pip-python install termcolor
    $ git clone git://github.com/yahoo/Openstack-DevstackPy.git DevstackPy
    $ cd DevstackPy

# Actions

*Stack* can do the following:

* __install__ OpenStack components
* __uninstall__ OpenStack components (from a previous *stack* install)
* __start__ OpenStack components (from a previous *stack* install)
* __stop__ OpenStack components (from a previous *stack* start)

Typically the interaction would be that you install a set of components and then start them. 

# Simple setup

https://github.com/yahoo/Openstack-DevstackPy/wiki/Simple-Setup

# Config

For those of you that are brave enough to change *stack* here are some starting points.

###  conf/stack.ini

Check out *conf/stack.ini* for various configuration settings applied (branches, git repositories...).  Check out the header of that file for how the customized configuration values are parsed and what they may result in.

### conf/

Check out *conf/* for various component specific settings and files. 

Note that some of these files are templates (ones ending with *.tpl*).
These files may have strings of the format *%NAME%* where *NAME* will most often be adjusted to a real value by the *stack* script.  

An example where this is useful is say for the following line:

       admin_token = %SERVICE_TOKEN% 

Since the script will either prompt for this value (or generate it for you) we can not have this statically set in a configuration file. 

### conf/pkgs

Check out *conf/pkgs* for package listings and *conf/pips* for python packages for various distributions. 

Note that these files are in a modified json format which allows for simple comments (lines starting with *#*). These comments are useful for explanations of why a version was chosen or the like.

# Starting

**!Installing in a dedicated, disposable vm is safer than installing on your dev machine!**

1. Get and install the above prerequisites.
1. *git clone git://github.com/yahoo/Openstack-DevstackPy.git*

# Customizing

You can override environment variables used in *stack* by editing *stack.ini* or by sourcing a file that contains your environment overrides before your run *stack*.

## Logging

To adjust logging edit the *conf/logging.ini* file which controls the logging levels and handlers. 

* You can also change which logging file name python will select ([format defined here](http://docs.python.org/dev/library/logging.config.html)) by setting the environment variable *LOG_FILE*.

# We want more information!

Please check out: <https://github.com/yahoo/Openstack-DevstackPy/wiki>
