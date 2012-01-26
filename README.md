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
       -c COMPONENT, --component=COMPONENT
                             openstack component, ie (db, glance, horizon, keystone,
                             keystone-client, nova, nova-client, novnc, openstack-x,
                             quantum, rabbit, swift)
     
       Install/uninstall/start/stop options:
         -a ACTION, --action=ACTION
                             action to perform, ie (install, start, stop, uninstall)
         -d DIR, --directory=DIR
                             empty root DIR for install or DIR with existing
                             components for start/stop/uninstall
         -i, --ignore-deps   ignore dependencies when performing ACTION
         -e, --ensure-deps   ensure dependencies when performing ACTION (default:
                             True)
         -r COMPONENT, --ref-component=COMPONENT
                             component which will not have ACTION applied but will be
                             referenced as if it was (ACTION dependent)
     
       Uninstall/stop options:
         -f, --force         force ACTION even if no trace file found
     
       Miscellaneous options:
         --list-deps         show dependencies of COMPONENT (default: False)
         --describe-components
                             describe COMPONENT (default: False)

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

# Q/A

## Why are we doing this?

1. The current devstack v1 seems to be growing into something it was never meant to be and is becoming hard to understand.
1. A python implementation will:
    * Reign the above in and match closely how the other openstack components are developed, tested and code reviewed.
    * Keep openstack on one language, thus reducing the language complexity aspect.
1. Additional features/nice to haves were added:
    * Ability to uninstall/start/stop the different components.
    * Command line help and descriptions of components.
    * An object oriented model that can be *easily* examined to figure out what a component requires for setup/config/install/starting/stopping.
1. It can be a place where distributions will come to determine exactly what packages where used for a given openstack release (thus the reason why full versions are important).
1. It can also be a place where you find out what openstack components have dependencies on other components:
    * For example: glance depends on keystone, glance depends on a database, keystone depends on a database...

## Why not just rely on package management dependency systems?

1. Having the dependency's handled by the distribtion package management system makes it **hard** for others to know what **exactly** is installed and what should exactly be installed. 
    * This is important just in general since not everyone is on ubuntu 11.10 (or later), especially for development.
    * This is one of the *key* problems that we are trying to solve, since developers are on systems other than ubuntu and those individuals/companies want to contribute to openstack.
        * How can these individuals/companies do that if they can't easily get a development system with dependencies installed up and running. This issue 
          seems like it was starting to be addressed by devstack v1 with apt package lists but this does not seem complete enough as knowing the exact 
          versions of packages is also very important for other distributions to know what version they should provide. 
          Thus the reason for having dependencies + versions (not a complete dependency graph) listed.
1. It allows developers to have reproducibility.
    * For example when a bug is filed against diablo (or other release/milestone), the developer can easily figure out exactly what packages where installed for whichever distribution that bug was filed against
      This allows that developer to recreate the bug (or have a chance at recreated it) and rule out dependency issues causing that bug.
1. Those dependency management systems do not always work the same, so the intricacies of how they work can be isolated in the devstack code.

## Why not just rely on dep or rpm files?

1. Devstack was created for developers and these developers will most likely be using trunk code.
1. Some of the intricacies with getting openstack running, the configs setup, ..., are not as simple as just over-writing some config files (some require actual logic to determine what to do).
    * This is why its not as simple as just having a set of debian packages or rpm's that hand-code this logic in there packaging language.
1. This also violates the *key* principle that openstack seems to be sticking to, that of of keeping openstack projects under python if at all possible.
    
**Past experience**

Something yahoo has learned from doing this many different ways (more than you want to know) is that in the end when having a production level software that can be installed (repeatedly) requires at information on exactly what versions/packages/dependencies are needed. If a distribution automatically updates a package version without the openstack community knowing & approving that change and we didn't list the versions then it may crash openstack (or at least invalidate tests that the openstack community has tested with a given set of dependencies+versions).

That is one of the major wins for versions and dependency lists. Since openstack will be developed and deployed on more than one distribution having a central place where people know exactly what packages + versions worked for a release (or for development) seems pretty important (especially as the project matures). This may be an *inversion* of currently how it works but it seems better to fix this now than later when it becomes even more of a problem.
