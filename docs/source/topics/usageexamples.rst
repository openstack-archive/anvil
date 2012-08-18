.. _usage-examples:

===============
Usage Examples
===============


Commands
--------

To get the help display try:

::

     $ ./smithy --help

To examine what installing the basics (nova, horizon, glance, keystone…)
will do (with installation in ``~/openstack``) try:

::

     $ sudo ./smithy -d ~/openstack -a install --dryrun  

With more information via debug statements output try:

::

     $ sudo ./smithy -d ~/openstack  -a install -v
