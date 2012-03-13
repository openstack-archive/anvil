# Contributing to DEVSTACKpy

## General

DEVSTACKpy is written in python (we should be compatible with ``python >= 2.6``).

DEVSTACKpy's official repository is located on GitHub at
https://github.com/yahoo/Openstack-DevstackPy.git. 

Besides the master branch that tracks the OpenStack ``trunk`` branches will maintained for all
OpenStack releases starting with Essex (stable/essex).

The primary script in DEVSTACKpy is ``stack``, which performs the bulk of the
work for DevStack's use cases (it acts as the main program entrypint).  

A number of additional scripts can be found in the ``tools`` directory that may
be useful for other tasks related to DEVSTACKpy.

## Documentation

Please create documentation on the GitHub wiki located at:

https://github.com/yahoo/Openstack-DevstackPy/wiki

This will suffice until a more *official* documentation site can be made.

## Style

* Please attempt to follow [pep8] for all code submitted.
 * ``./run_tests.sh  -p``

* Please also attempt to run [pylint] all code submitted.
 * ``./run_tests.sh  -l``

* Please also attempt to run the json validation all changes to pip/pkgs json files submitted.
 * ``./run_tests.sh  -j``

## Tests

To run our limited set of tests (WIP) use the following command:

    ./run_tests.sh 
    
## Environment Variables

* The ``OS_*`` environment variables should be the only ones used for all
  authentication to OpenStack clients as documented in the [CLI Auth] wiki page.
  
## Documentation

Documentation should all be written in [markdown]. Although github does support other formats it seems better just to stabilize on one.

[CLI Auth]: http://wiki.openstack.org/CLIAuth
[pep8]: http://www.python.org/dev/peps/pep-0008/
[pylint]: http://pypi.python.org/pypi/pylint
[markdown]: http://daringfireball.net/projects/markdown/
