.. _q-a:

===============
Questions and Answers
===============

Can I use ANVIL for production?
------------------------------------

Up to u! Beware of the sea and the black waters!

How do I get program usage?
---------------------------

::

     $ ./smithy --help

How do I run a specific OpenStack milestone?
--------------------------------------------

OpenStack milestones have tags set in the git repo. Set the appropriate
setting in the **branch** variables in *conf/anvil.ini*.

**Note:** Swift is on its own release schedule so pick a tag in the
Swift repo that is just before the milestone release.

For example:

::

    # Quantum client git repo
    quantum_client_repo = git://github.com/openstack/python-quantumclient.git
    quantum_client_branch = essex-3

    # Melange service
    melange_repo = git://github.com/openstack/melange.git
    melange_branch = essex-3

    # Python melange client library
    melangeclient_repo = git://github.com/openstack/python-melangeclient.git
    melangeclient_branch = essex-3

OMG the images take forever to download!
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