Devstack v2 is a set of python scripts and utilities to quickly deploy an OpenStack cloud.

# Goals

* To quickly build dev OpenStack environments in a clean environment (as well as start, stop, and uninstall those environments)
* To describe working configurations of OpenStack (which code branches work together?  what do config files look like for those branches? what packages are needed for installation?)
* To make it easier for developers to dive into OpenStack so that they can productively contribute without having to understand every part of the system at once
* To make it easy to prototype cross-project features

Read more at <http://devstack.org> (TBD)

IMPORTANT: Be sure to carefully read *stack* and any other scripts you execute before you run them, as they install software and may alter your networking configuration.  We strongly recommend that you run stack in a clean and disposable vm when you are first getting started.

# Help

In order to determine what *stack* can do run the following.

    ./stack --help
 
This will typically produce:

    ./stack --help
    Usage: stack [options]
    
    Options:
      --version             show program's version number and exit
      -h, --help            show this help message and exit
      -a ACTION, --action=ACTION
                            action to perform, ie (install, start, stop,
                            uninstall)
      -d DIR, --directory=DIR
                            root DIR for new components or DIR with existing
                            components (ACTION dependent)
      -c COMPONENT, --component=COMPONENT
                            stack component, ie (db, glance, horizon, keystone,
                            nova, quantum, rabbit, swift)
      -f, --force           force ACTION even if no trace found (ACTION dependent)

# Stack prerequisites

* easy_install termcolor (used for colored console logging)
* easy_install netifaces (used to determine host ip information)

# Actions

You will note that *stack* can uninstall, install, start and stop openstack components. Typically the interaction would be that you install a set of components and then start them. 

# Config

If you want to change which devstack branches or other various devstack configurations. 
Check out *conf/stack.ini* for various configuration settings applied (branches, git repositories...).
When you see a configuration in *stack.ini* with the format *${NAME:-DEFAULT}* this means that the environment the *stack* script is running in while be referred to and if that value exists it will be used (otherwise the *DEFAULT* will be used).
Also check out *conf/* for various component specific settings and *conf/pkgs* for package listings (with versions) for various distributions.

# To start a dev cloud (Installing in a dedicated, disposable vm is safer than installing on your dev machine!):

    ./stack -a install -d $HOME/openstack && ./stack -a start -d $HOME/openstack 

When the script finishes executing, you should be able to access OpenStack endpoints, like so:

* Horizon: http://myhost/
* Keystone: http://myhost:5000/v2.0/

# Customizing

You can override environment variables used in *stack* by editing *stack.ini* or by sourcing a file that contains your overrides before your run *stack*.
