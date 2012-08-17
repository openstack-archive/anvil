.. _q-a:

===============
Questions and Answers
===============

How do I get program usage?
---------------------------

::

     $ ./smithy --help

How do I run a specific OpenStack milestone?
--------------------------------------------

OpenStack milestones have tags set in the git repo. Anvil also has the same
tags so please checkout the corresponding tag for anvil to match the OpenStack
milestone you wish to use.

`OMG` the images take forever to download!
----------------------------------------

Sometimes the images that will be uploaded to glance take a long time to
download and extract and upload.

To adjust this edit *conf/anvil.ini* and change the following:

::

    [img]

    ...

    # uec style cirros 0.3.0 (x86_64) and ubuntu oneiric (x86_64)
    image_urls = http://launchpad.net/cirros/trunk/0.3.0/+download/cirros-0.3.0-x86_64-uec.tar.gz, http://uec-images.ubuntu.com/oneiric/current/oneiric-server-cloudimg-amd64.tar.gz

To something like the following:

::

    [img]

    ...

    # uec style cirros 0.3.0 (x86_64) 
    image_urls = http://launchpad.net/cirros/trunk/0.3.0/+download/cirros-0.3.0-x86_64-uec.tar.gz

This will remove the larger ubuntu image and just use the smaller
`cirros`_ image (which should not take to long to upload).

.. _cirros: https://launchpad.net/cirros