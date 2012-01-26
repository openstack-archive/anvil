*Devstack v2* is a set of python scripts and utilities to quickly deploy an OpenStack cloud.

# Goals

* To quickly build dev OpenStack environments in a clean environment (as well as start, stop, and uninstall those environments) with as little baggage as possible.
* To describe working configurations of OpenStack.
    * Which code branches work together? 
    * What do config files look like for those branches? 
    * What packages are needed for installation for a given distribution?
* To make it easier for developers to dive into OpenStack so that they can productively contribute without having to understand every part of the system at once.
* To make it easy to prototype cross-project features.

Read more at <http://devstack.org> (TBD) or <https://github.com/yahoo/Openstack-Devstack2/wiki>

**IMPORTANT:** Be sure to carefully read *stack* and any other scripts you execute before you run them, as they install software and may alter your networking configuration.  We strongly recommend that you run stack in a clean and disposable vm when you are first getting started. (*TODO* dry-run mode would be great!).

# Help

In order to determine what *stack* can do for you run the following.

    ./stack --help
 
This will typically produce:
    
     Usage: stack [options]
     
     Options:
       --version             show program's version number and exit
       -h, --help            show this help message and exit
     
       Install/uninstall/start/stop options:
         -a ACTION, --action=ACTION
                             action to perform, ie (install, start, stop, uninstall)
         -d DIR, --directory=DIR
                             empty root DIR for install or DIR with existing
                             components for start/stop/uninstall
         -c COMPONENT, --component=COMPONENT
                             openstack component, ie (db, glance, horizon, keystone,
                             keystone-client, nova, nova-client, openstack-x,
                             quantum, rabbit, swift)
         -i, --ignore-deps   ignore dependencies when performing ACTION
         -e, --ensure-deps   ensure dependencies when performing ACTION (default:
                             True)
         -r COMPONENT, --ref-component=COMPONENT
                             component which will not have ACTION applied but will be
                             referenced as if it was (ACTION dependent)
     
       Uninstall/stop options:
         -f, --force         force ACTION even if no trace file found
     
       Dependency options:
         -s, --list-deps     show dependencies of COMPONENT (default: False)

# Stack prerequisites

* linux (tested on ubuntu 11 (aka oneiric) and rhel 6.2 (TBD))
* python 2.6 or 2.7 (not tested with python 3.0)
* git
    * In ubuntu oneiric *apt-get install git*
* easy_install termcolor (used for colored console logging)
    * In ubuntu oneiric *apt-get install python-pip*
* easy_install netifaces (used to determine host ip information)
    * In ubuntu oneiric *apt-get install python-pip* and *apt-get install python-dev*
 
# Actions

*Stack* can do the following:

* __install__ OpenStack components
* __uninstall__ OpenStack components (from a previous *stack* install)
* __start__ OpenStack components (from a previous *stack* install)
* __stop__ OpenStack components (from a previous *stack* start)

Typically the interaction would be that you install a set of components and then start them. 

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

Note that these files are in a modified json format which allows for simple comments (lines starting with #).
These comments are useful for explanations of why a version was chosen or the like.

# Starting

**!Installing in a dedicated, disposable vm is safer than installing on your dev machine!**

1. Get ubuntu 11 (oneiric) or redhat 6 (or equivalent) and create a new machine/vm with that distribution
1. Install the above prerequisites
1. *git clone git://github.com/yahoo/Openstack-Devstack2.git*

## Glance

### Installing

1. Run: *./stack -a install -d $HOME/openstack -c glance*
    * *Note:* This will also install glances dependencies (to show dependencies run *./stack -s*)
        * If this is undesired try the *--ignore-deps* option
1. When prompted for passwords either press enter (to have it generate one) or enter a password.
1. Wait for it to finish...
    * On finish you should see all configurations/passwords/database dsn's that have been fetched (for future reference). 

You will also see a set of directories that end with *traces*.  
These directories contain files with the actions of exactly what occurred (files touched, directories created, packages installed).  
They are used for knowing what occurred and also for *stack's* uninstalling process. 

An example of this end state is the following:

    INFO: @devstack : Finished install of glance - check /tmp/openstack/glance/traces for traces of what happened.
    INFO: @devstack : After install your config is:
    INFO: @devstack : Passwords:
    INFO: @devstack : 	horizon_keystone_admin@passwords=8fc354d015dc94f2
    INFO: @devstack : 	service_token@passwords=a1b1557b1cb0e67b
    INFO: @devstack : 	sql@passwords=c910be697958ccb7
    INFO: @devstack : Configs:
    INFO: @devstack : 	glance_branch@git=master
    INFO: @devstack : 	glance_repo@git=https://github.com/openstack/glance.git
    INFO: @devstack : 	host_ip@default=
    INFO: @devstack : 	keystone_branch@git=stable/diablo
    INFO: @devstack : 	keystone_repo@git=https://github.com/openstack/keystone.git
    INFO: @devstack : 	port@db=3306
    INFO: @devstack : 	sql_host@db=localhost
    INFO: @devstack : 	sql_user@db=root
    INFO: @devstack : 	syslog@default=0
    INFO: @devstack : 	type@db=mysql
    INFO: @devstack : Data source names:
    INFO: @devstack : 	glance=mysql://root:c910be697958ccb7@localhost:3306/glance
    INFO: @devstack : 	keystone=mysql://root:c910be697958ccb7@localhost:3306/keystone
    INFO: @devstack : Finished action [install] on Fri, 20 Jan 2012 18:29:12
    INFO: @devstack : Check [/tmp/openstack/db/traces, /tmp/openstack/keystone/traces, /tmp/openstack/glance/traces] for traces of what happened.
   
### Starting

1. Run *./stack -a start -d $HOME/openstack -c glance*
    * *Note:* This will also start glances dependencies (to show dependencies run *./stack -s*)
        * If this is undesired try the *--ignore-deps* option
    * *Note:* Currently forking is done instead of running screen (*TODO* get screen working)
1. On finish you should see a list of files which will have information about what is started
    * For forking mode this will be a file with information on where the PID is, where the STDERR/STDOUT files are.
    
An example of one of these files is the following:

    $ cat /tmp/openstack/glance/traces/glance-api.fork.trace
      RUN - FORK
      PID_FN - /tmp/openstack/glance/traces/glance-api.fork.pid
      STDERR_FN - /tmp/openstack/glance/traces/glance-api.fork.stderr
      STDOUT_FN - /tmp/openstack/glance/traces/glance-api.fork.stdout


### Stopping

1. Run *./stack -a stop -d $HOME/openstack -c glance*
    * *Note:* This will also stop glances dependencies (to show dependencies run *./stack -s*)
        * If this is undesired try the *--ignore-deps* option

On finish you should see something like the following:

    INFO: @devstack.component : Stopping glance-registry
    INFO: @devstack.runners.fork : Attempting to kill pid 17282
    INFO: @devstack.runners.fork : Sleeping for 1 seconds before next attempt to kill pid 17282
    INFO: @devstack.runners.fork : Attempting to kill pid 17282
    INFO: @devstack.runners.fork : Killed pid 17282 after 2 attempts
    INFO: @devstack.runners.fork : Removing pid file /tmp/openstack/glance/traces/glance-registry.fork.pid
    INFO: @devstack.runners.fork : Removing stderr file /tmp/openstack/glance/traces/glance-registry.fork.stderr
    INFO: @devstack.runners.fork : Removing stdout file /tmp/openstack/glance/traces/glance-registry.fork.stdout
    INFO: @devstack.runners.fork : Removing glance-registry trace file /tmp/openstack/glance/traces/glance-registry.fork.trace
    INFO: @devstack.component : Deleting trace file /tmp/openstack/glance/traces/start.trace

### Uninstalling

1. Run *./stack -a uninstall -d $HOME/openstack -c glance*
    * *Note:* This will also uninstall glances dependencies (to show dependencies run *./stack -s*)
        * If this is undesired try the *--ignore-deps* option
    * *Note:* This may also require *sudo* access to cleanup all the necessary directories that python sets up.

On finish you should see something like the following:

    INFO: @devstack.component : Removing 2 configuration files
    INFO: @devstack : Uninstalling glance.
    INFO: @devstack.component : Potentially removing 29 packages
    INFO: @devstack.component : Removing 1 touched files
    INFO: @devstack.component : Uninstalling 1 python setups
    INFO: @devstack.component : Removing 3 created directories
    INFO: @devstack : Finished action [uninstall] on Fri, 20 Jan 2012 19:15:43

# Customizing

You can override environment variables used in *stack* by editing *stack.ini* or by sourcing a file that contains your environment overrides before your run *stack*.

## Logging

To adjust logging edit the *conf/logging.ini* file which controls the logging levels and handlers. 

* You can also change which logging file name python will select ([format defined here](http://docs.python.org/dev/library/logging.config.html)) by setting the environment variable *LOG_FILE*.
