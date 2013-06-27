.. _q-a:

=====================
Questions and Answers
=====================

How do I cause the anvil dependencies to be reinstalled?
--------------------------------------------------------

Anvil bootstraps itself via shell script (if you look at the code
in the file ``smithy`` you will see that it is actually a bash
script).

This bootstrapping occurs to ensure that anvils pypi/rpm/deb
dependencies are installed before anvil can actually be used. 
To remove the files that are left behind to let the shell script
know when this happens delete files located at ``$HOME/.anvil_bootstrapped``
and at ``$PWD/.anvil_bootstrapped`` to cause bootstrapping to occur again.

Another way to make this happen temporarily is to use the following:

::

    sudo BOOT_FILES=/dev/null ./smithy

This will make anvil think those files are coming from ``/dev/null``
which will always return nothing. Using the same variable
also allows you to retarget the locations where the ``smithy``
shell script will look for the 'marker' files if 
you so choose (say in a continuous integration environment).


How do I run a specific OpenStack milestone?
--------------------------------------------

Anvil has the same tag names as OpenStack releases so to
run against a specific milestone of OpenStack just checkout the
same tag in anvil and run the same actions as
you would have ran previously. 

An example of this, lets adjust nova to use the ``stable/essex`` branch.

- Open ``conf/components/nova.yaml`` in your favorite editor
- Locate the line that starts with ``get_from:`` and either change
  it to a new github location

::

    # Where we download this from...
    get_from: "git://github.com/openstack/nova.git?branch=stable/essex"


- The special keywords here are ``branch=``
  and ``tag=`` which are ways for anvil to parse out which branch/tag
  you desire. 

  - **Note:** this is not git official syntax
  - **Note:** tag overrides branch (so you can't really include both)


`OMG` the images take forever to download!
------------------------------------------

Sometimes the images that will be uploaded to glance take a long time to
download and extract and upload.

To adjust this edit ``conf/components/glance.yaml`` and change the following:

::

    ...
    # List of images to download and install into glance.
    image_urls:
    - http://launchpad.net/cirros/trunk/0.3.0/+download/cirros-0.3.0-x86_64-uec.tar.gz
    - http://smoser.brickies.net/ubuntu/ttylinux-uec/ttylinux-uec-amd64-11.2_2.6.35-15_1.tar.gz

To something like the following (shortening that list):

::

    image_urls:
    - http://launchpad.net/cirros/trunk/0.3.0/+download/cirros-0.3.0-x86_64-uec.tar.gz

This will remove the larger ubuntu image and just use the smaller `cirros`_ image (which should not take to long to upload). 
Note that repeated downloads occur due to the fact that the files inside the image do not match the name of what is installed
into glance (this can be avoided by completely disabling the image uploading, see the persona file for the flag for this).

.. _cirros: https://launchpad.net/cirros
