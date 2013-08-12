.. _summary:

===============
Summary
===============

Anvil is a forging tool to help build OpenStack components and there
dependencies into a complete system.

It git checkouts the OpenStack components, analyzes & builds there dependencies and the 
components themselves into packages. It then can install from the package repositories
it created, perform configuration and start, stop, restart and all the OpenStack 
as a complete system.

It allows a developer to install there environment using said packages 
(and dependencies) and anvil then automatically configures the components to 
work correctly for the developers needs. After the developer has tested out their
features or changes they can then stop the OpenStack components, uninstall the
packages and bring back their system to a pre-installation/pre-anvil state.

The distinguishing part from devstack_ (besides being written in python and not
shell), is that after building those packages  (currently rpms) the same packages
can be used later (or at the same time) to  actually deploy at a larger scale with.

.. _devstack: http://www.devstack.org/
