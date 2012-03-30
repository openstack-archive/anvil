.. _usage-examples:

===============
Usage Examples
===============


Commands
--------

To get the ``stack`` help display try:

::

     $ ./stack --help

To examine what installing the basics (nova, horizon, glance, keystone…)
will do (with installation in ``~/openstack``) try:

::

     $ sudo ./stack -d ~/openstack -a install --dryrun  

With more information/debugging/auditing output try:

::

     $ sudo ./stack -d ~/openstack  -a install -vv 
