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

An example of this, lets adjust ``nova`` to use the ``stable/essex`` branch.

- Open ``conf/origins/master.yaml`` file in your favorite editor
- Locate lines that describe the ``nova`` component
- Change branch parameter to the desired one

::

    nova:
        repo: https://github.com/openstack/nova.git
        branch: stable/essex

- Component origin parameters are:
    - ``repo: <repo_url>`` - required
    - ``branch: <branch>`` - optional
    - ``tag: <tag>`` - optional

  If no branch nor tag parameters were specified then ``branch: master`` is used by default.

  **Note:** tag overrides branch (so you can't really include both)
