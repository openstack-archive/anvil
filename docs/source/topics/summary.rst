.. _summary:

===============
Summary
===============

Anvil is a forging tool to help build OpenStack components and their
dependencies into a complete package-oriented system.

It automates the git checkouts of the OpenStack components, analyzes & builds their
dependencies and the components themselves into packages. It then can install 
from the package repositories it created, perform configuration and start, stop,
restart and uninstall the components and their dependencies as a complete system.

It allows a developer to setup an environment using the automatically created packages
(and dependencies) with the help of anvil configuring the components to work
correctly for the developer's needs. After the developer has tested out their
features or changes they can stop the OpenStack components, uninstall the
packages and bring back their system to a pre-installation/pre-anvil state.

The distinguishing part from devstack_ (besides being written in Python and not
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
