multipip
========

`pip` utility refuses to handle multiple requirements for one package::

    $ pip install 'nose>=1.2' 'nose>=2' 'nose<4'
    Double requirement given: nose>=2 (already in nose>=1.2, name='nose')

Use `multipip` to join these requirements::
    
    $ multipip 'nose>=1.2' 'nose>=2' 'nose<4'
    nose>=2,<4

Files of requirements can be used as well::

    $ cat pip-requires 
    nose<4
    $ multipip 'nose>=1.2' 'nose>=2' -r pip-requires 
    nose>=2,<4

`multipip` prints error messages for incompatible requirements to
stderr and chooses the first one::

    $ cat pip-requires 
    pip==1.3
    $ multipip 'pip==1.2' -r pip-requires 
    pip: incompatible requirements
    Choosing:
    	command line: pip==1.2
    Conflicting:
    	-r pip-requires (line 1): pip==1.3
    pip==1.2
    
It is possible to filter some packages from printed output. This can
be useful for a huge `pip-requires` file::

    $ cat pip-requires 
    nose<4
    pip==1.2
    nose>=1.2
    $ multipip -r pip-requires --ignore-packages nose
    pip==1.2

Installed packages can be filtered, too (they are taken from `pip
freeze`)::

    $ cat pip-requires 
    nose<4
    pip==1.2
    nose>=1.2
    $ pip freeze | grep nose
    nose==1.1.2
    $ multipip -r pip-requires --ignore-installed
    pip==1.2
    
py2rpm
======

Distutils provides an interface for building RPMs::

    $ python ./setup.py bdist_rpm

This tool has several problems:
* Red Hat based distros use different package names, e.g.,
  `python-setuptools` instead of `distribute`, `python-nose` instead
  of `nose` and so on;
* `Requires` and `Conflicts` sections for generated RPM are incorrect;
* sometimes not all required files are packaged;
* miscellaneous problems with man files;
* package directory in `/usr/lib*/python*/site-packages/<pkg>` is not
  owned by any RPM;
* some packages (like selenium) are architecture dependent but
  `bdist_rpm` generates `BuildArch: noarch` for them.

`py2rpm` is aimed to solve all these problems.

`py2rpm` accepts a list of archive names or package directories and
builds RPMs (current directory is used by default)::

    $ py2rpm
    ...
    Wrote: /home/guest/rpmbuild/SRPMS/python-multipip-0.1-1.src.rpm
    Wrote: /home/guest/rpmbuild/RPMS/noarch/python-multipip-0.1-1.noarch.rpm
    ...
