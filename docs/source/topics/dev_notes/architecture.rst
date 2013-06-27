.. _architecture:

========================
How anvil is architected
========================

This little ``HOWTO`` can be used by those who wish to
understand how anvil does things and why some of its
architectural decisions were made.

Diving in!
----------

^^^^^^^^^^^^^^^^
A little history
^^^^^^^^^^^^^^^^

Once upon a time there was a idea of replacing the then existing `devstack <http://devstack.org/>`_
with a more robust, more error-tolerant and more user/developer friendly OpenStack
setup toolkit. Since the existing `devstack <http://devstack.org/>`_ did (and still
does not support very well) complex intercomponent (and interpackage management system) dependencies
and installing/packaging/starting/stopping/uninstalling of OpenStack components.

To solve this problem it was thought that there could be a toolkit that could handle this better.
It would also be in Python the language of choice for the rest of the OpenStack components thus making
it easier to understand for programmers who are already working in OpenStack code. Thus *devstack2* was
born which was later renamed *devstack.py* and after a  little while once again got renamed to *anvil*.

^^^^^^^^^
Structure
^^^^^^^^^

Anvil is designed to have the following set of software components:

* **Actions:** an action is a sequence of function calls on a set of implementing
  classes which follows a logically flow from one step to the next. At the end of 
  each step an action may choose to negate a step of another action. 

  * Preparing

    * Downloading source code
    * Post-download patching of the source code
    * Deep dependency & requirement analysis
    * Downloading and packaging of missing python dependencies
    * Packaging downloaded source code
    * Creation of a repository with all built packages & dependencies

  * Install

    * Configuring
    * Pre-installing
    * Installing packages from previously prepared repository
    * Post-installing

  * Uninstall

    * Unconfiguring
    * Pre-uninstalling
    * Uninstalling previously installed packages
    * Post-uninstalling

  * Starting

    * Pre-starting
    * Starting
    * Post-starting

  * Stopping
  * Testing
  * Packaging

* **Phases:** a phase is a step of an action which can be tracked as an individual
  unit and can be marked as being completed. In the above install action for each
  component that installed when each step occurs for that component it will be recorded
  into a file so that if ``ctrl-c`` aborts anvil and later the install is restarted
  anvil can notice that the previous phases have already been completed and those
  phases can be skipped. This is how anvil does action and step resuming.

* **Components:** a component is a class which implements the above steps (which
  are literally methods on an instance) and is registered with the persona and 
  configuration to be activated. To aid in making it easier to add in new components
  a set of *generic* base classes exist that provide common functionality that
  should work in most simplistic installs. These can be found in 
  ``anvil/components/``. All current components that exist either use
  these base classes directly or inherit from them and override functions to 
  provide additional capabilities needed to perform the specified action.

* **Distributions:** a distribution is a yaml file that is tied to a operating
  system distribution and provides references for components to use in a generic
  manner. Some of these references include how to map a components ``pip-requires``
  file dependencies to distribution specific dependencies (possibly using ``yum``
  or ``apt``) or what non-specified dependencies are useful in getting the component
  up and running (such as ``guestfish`` for image mounting and manipulation).
  Other helpful references include allowing for components to specify standard 
  identifiers for configuration such as ``pip``. This allows the underlying yaml file to
  map the ``pip`` command to a distribution-centric command (in RHEL it its really
  named ``pip-python``), see the *commands* key in the yaml files for examples
  of these settings. Note that each distribution yaml file that exists in ``conf/distros``
  provides this set of references for each component and gets selected based on the
  yaml key in that file named *platform_pattern*.

* **Configuration:** central to how anvil operates is the ability to be largely
  configuration driven (code when you need it but avoid it if you can).
  Distributions as seen by the ``conf/distros`` folder specify
  distribution-specific *configuration* that can be referenced by standard keys by a given
  component. Each component also receives additonal configuration (accessible via a components
  ``get_option`` function) via the yaml files specified in ``conf/components`` which
  provides for a way to have configuration that is not distribution specific but instead
  is component specific (say for configuring *nova* to use kvm instead of qemu). This
  configuration drive approach (as much as can be possible) was a key design goal that
  drives how anvil was and is developed. It has even seemed to be ahead of its time due
  to how anvil has a distribution yaml file that has specified component dependencies
  long before the OpenStack community even recognized such a dependency list was useful.

* **Personas:** a persona is a way for anvil to know what components (and possibly 
  subsystems of those components) you wish to have the given action applied to. Since
  not everyone can agree on what is an install of OpenStack this concept allows for
  those who wish to have a different set to do so. It is as all other configuration
  another yaml file and can be examined by looking into the ``conf/personas`` folders. Each yaml file
  contains the list of components to be performed for the given action, a simple set of
  options for those components (for options that may not be applicable to be in the
  component configuration yaml) and which subsystems a given component will have enabled
  (if the component supports this concept) as well as which distribution the persona supports (if
  there is a desire to restrict a given persona to a given distribution this field can be
  used to accomplish that goal).
