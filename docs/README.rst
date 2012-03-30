=================
Building the docs
=================

Dependencies
============

Sphinx_
  You'll need sphinx (the python one) and if you are
  using the virtualenv you'll need to install it in the virtualenv
  specifically so that it can load the nova modules.

  ::

    pip install Sphinx


.. _Sphinx: http://sphinx.pocoo.org



Use `make`
==========

Just type make::

  % make html

Look in the Makefile for more targets.



Check out the `build` directory to find them. Yay!
