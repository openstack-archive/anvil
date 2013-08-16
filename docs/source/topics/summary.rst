.. _summary:

===============
Summary
===============

Anvil is a forging tool to help build OpenStack components and there
dependencies into a complete package-oriented system.

It automates the git checkouts the OpenStack components, analyzes & builds there
dependencies and the components themselves into packages. It then can install 
from the package repositories it created, perform configuration and start, stop,
restart and uninstall the components and there dependencies as a complete system.

It allows a developer to setup environment using the automatically created packages
(and dependencies) with the help of anvil configuring the components to work
correctly for the developers needs. After the developer has tested out their
features or changes they can then stop the OpenStack components, uninstall the
packages and bring back their system to a pre-installation/pre-anvil state.

The distinguishing part from devstack_ (besides being written in python and not
shell), is that after building those packages  (currently rpms) the same packages
can be used later (or at the same time) to  actually deploy at a larger scale using
tools such as chef_, salt_, or puppet_ (to name a few).

----

.. toctree::

   features


.. _devstack: http://www.devstack.org/
.. _puppet: http://puppetlabs.com/
.. _chef: http://www.opscode.com/chef/
.. _salt: http://saltstack.com/
