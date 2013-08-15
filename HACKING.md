# Contributing to Anvil

## General

Anvil is written in python (we should be compatible with ``python >= 2.6``).

Anvil's official repository is located on GitHub at: https://github.com/stackforge/anvil

Besides the master branch that tracks the OpenStack ``trunk`` tags will maintained for all OpenStack releases starting with `essex`.

The primary script in anvil is ``smithy``, which performs the bulk of the work for anvil's use cases (it acts as the main program entry-point).  

A number of additional scripts can be found in the ``tools`` directory that may or may not be useful to you.

## Documentation

Please create documentation in the ``docs/`` folder which will be synced with:

http://readthedocs.org/docs/anvil/

This will suffice until a more *official* documentation site can be made.

## Style

* Please attempt to follow [pep8] for all code submitted.
* Please also attempt to run [pylint] all code submitted.
* Please also attempt to run the [yaml] validation if you adjust any [yaml] files in the `conf` directory.

## Environment Variables

* The ``OS_*`` environment variables should be the only ones used for all authentication to OpenStack clients as documented in the [CLI Auth] wiki page.
  
## Documentation

Documentation should all be written in [markdown] or [rst]. Although github does support other formats it seems better just to stabilize on one of those.

## Style Commandments

1. Read http://www.python.org/dev/peps/pep-0008/
1. Read http://www.python.org/dev/peps/pep-0008/ again
1. Read on

### Overall

1. Put two newlines between top-level code (funcs, classes, etc)
1. Put one newline between methods in classes and anywhere else
1. Do not write "except:", use "except Exception:" at the very least
1. Include your name with TODOs as in "#TODO(termie)"
1. Do not name anything the same name as a built-in or reserved word
1. Do not use the '_' as a single character variable as it is used with
the [gettext] module and can lead to confusion if used for other purposes.

### Imports

1. Do not import objects, only modules (not strictly enforced)
1. Do not import more than one module per line
1. Do not make relative imports
1. Order your imports by the full module path
1. Organize your imports in lexical order


[gettext]: http://docs.python.org/2/library/gettext.html
[CLI Auth]: http://wiki.openstack.org/CLIAuth
[yaml]: http://en.wikipedia.org/wiki/YAML
[pep8]: http://www.python.org/dev/peps/pep-0008/
[pylint]: http://pypi.python.org/pypi/pylint
[markdown]: http://daringfireball.net/projects/markdown/
[rst]: http://docutils.sourceforge.net/docs/user/rst/quickstart.html

