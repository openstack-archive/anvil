.. _adding_own_distro:

====
Adding your own distribution
====

This little ``HOWTO`` can be used by those who wish to
add-on to anvil to be able to support there own distribution
or unsupported operating system (so that it can be
supported).

Diving in!
----------

First you have to have a little background on `anvil` and 
how it operates. So lets dive in and learn a little on how
we can add in your own distribution support.

**smithy**
  The main shell script that bootstraps the needed dependencies
  for anvil to be able to start (including items such as termcolor,
  progressbar and netifaces). The code here is written in bash shell
  script so that it can execute in an enviornment without the 
  needed prerequisites.

    **When to adjust:** Adjust the boot strapping functions in this file to install
    any needed prerequisites for your operating system to run anvil. Look at how we
    are bootstrapping rhel (and how we are detecting rhel) for an example.

**conf/distros**
  This set of yaml files contains definitions for what packages, 
  what pip to package mappings and what code entrypoints are used
  when setting up a given component. The critical key here is the
  ``platform_pattern`` key which is used as a regular expression to
  determine if the provided yaml file will work in the given running
  distribution. Other keys are used to identify which packaging class
  to use (ie ``packager_name``) and how to map a component name to
  its action classes (ie ``action_classes/install`` will be constructed
  when an install action occurs). The ``commands`` section can be used to
  `house` arbitrary commands which may vary between operating systems (such
  as the ``pip`` executable name)

    **When to adjust the distro:** If a suitable distribution already exists (which may be the case
    for many rhel variants), just go ahead and add-on to the regular expression your pattern. Ensure
    that your regular expressionmatches the output of the following command: ``python -c "import platform; print(platform.platform())"``
    which is what anvil uses internally to match a given yaml file to a given distribution.

    **When to add a new file:** If no suitable distribution exists (which may be the case
    for ubuntu), you will need to go ahead and create a new file for that distribution and
    include its dependencies and any variations in packaging and pip -> package mappings needed
    to setup that distribution with the openstack component software.

**anvil/distros**
  These are typically subclasses of components that may override generic functionality to correct
  for a given distribution doing or requiring something different to occur before/after or during
  an install or other action. 

  **When to adjust:** Feel free to add-on your own subclasses here as needed to handle any special actions
  that your new distribution may require and make sure you reference those classes/entrypoints 
  in your **conf/distros** yaml file so that the correct subclass will be used. The rhel distro has a good set
  of examples that overload various key points so that rhel can work correctly.

**anvil/packaging**
  The modules in this folder will be referenced in your **conf/distros** yaml file and will control
  how to install packages (ie using yum and pip) and how to uninstall those same packages. This code will also
  get activated when a 'package' action occurs which currently will cause the necessary actions to occur to 
  create a rpm ``spec`` file which can be used with the ``rpmbuild`` command.

  **When to adjust:**  If needed it should be simple to look at the packaging interface and add your own.
  After adding make sure you reference them in your **conf/distros** yaml file so that the correct subclass will be used. If you are going
  to want to create package files from the installed code then you will need to hook-in to a file similar
  to the rpm module that exists there. 
