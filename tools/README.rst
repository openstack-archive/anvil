**Anvil utility toolbelt**
==========================

multipip
--------

`pip` utility refuses to handle multiple requirements for one package::

    $ pip install 'nose>=1.2' 'nose>=2' 'nose<4'
    Double requirement given: nose>=2 (already in nose>=1.2, name='nose')

Use `multipip` to join these requirements::

    $ multipip 'nose>=1.2' 'nose>=2' 'nose<4'
    nose>=2,<4


`multipip` can be used to run `pip`::

   $ pip install $(multipip -r pip-requires)
   ...

Files of requirements can be used as well::

    $ cat pip-requires
    nose<4
    $ multipip 'nose>=1.2' 'nose>=2' -r pip-requires
    nose>=2,<4

`multipip` prints error messages for incompatible requirements to
stderr and chooses the first one (note: command-line requirements take
precedence over files)::

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
------

Distutils provides an interface for building RPMs::

    $ python ./setup.py bdist_rpm

This tool has several problems:

* Red Hat based distros use different package names, e.g.,
  `python-setuptools` instead of `distribute`, `python-nose` instead
  of `nose` and so on...
* `Requires` and `Conflicts` sections for generated RPM are incorrect.
* Sometimes not all required files are packaged.
* Miscellaneous problems with man files;
* Package directory in `/usr/lib*/python*/site-packages/<pkg>` is not
  owned by any RPM;
* Some packages (like selenium) are architecture dependent but
  `bdist_rpm` generates `BuildArch: noarch` for them.

`py2rpm` is aimed to solve all these problems.

`py2rpm` accepts a list of archive names or package directories and
builds RPMs (current directory is used by default)::

    $ py2rpm
    ...
    Wrote: /home/guest/rpmbuild/SRPMS/python-multipip-0.1-1.src.rpm
    Wrote: /home/guest/rpmbuild/RPMS/noarch/python-multipip-0.1-1.noarch.rpm
    ...


yyoom
-----

`yyoom` uses the yum API to provide nice command-line interface to package
management. It is able to install and remove packages in the same
transaction (see `yyoom transaction --help`), list available or installed
packages and a bit more. It writes results of its work to standard output
in JSON (which is much easier to use from other programs).

`yyoom` is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

yumfind
-------

`yumfind` uses the yum API to provide a interface to finding packages in the
yum repository that may match a given name or a given name with a set of python
requirements. It writes results of its work to standard output
in JSON or in rpm package name format (see `yumfind --help`)::

    $ ./tools/yumfind -p 'python-setuptools,setuptools>0.8,<1'
    python-setuptools-0.9.8-0.el6.noarch
    $ ./tools/yumfind -p 'python-setuptools,setuptools>0.8,<1' -j
    {"release": "0.el6", "epoch": "0", "version": "0.9.8", "arch": "noarch", "name": "python-setuptools"}

`yumfind` is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

pip-download
------------

`pip-download` is a small helper utility that interacts with pip and the pip API to
download packages into a given directory (using a common extraction and download
cache subdirectories). It also automatically prunes duplicated downloads if they
are of the same project name (which pip appears to do sometimes, such as in the distribute
and setuptools fiasco). This helps avoid needless duplication::

    $ ./tools/pip-download -d /tmp/e 'setuptools>0.8' 'flake8'
    Saved /tmp/e/flake8-2.0.tar.gz
    Saved /tmp/e/mccabe-0.2.1.tar.gz
    Saved /tmp/e/pep8-1.4.6.tar.gz
    Saved /tmp/e/pyflakes-0.7.3.tar.gz
    Saved /tmp/e/setuptools-0.9.8.tar.gz


specprint
---------

`specprint` uses the rpm API to provide a interface to printing the details
of an rpm spec file in a easy to parse format. It writes results of its work to
standard output in JSON (which is much easier to use from other programs)::

    $ ./tools/specprint -f python.spec
    {
        "headers": {
            "arch": "x86_64",
            "description": "Python is an interpreted, interactive, object-oriented programmin....",
            "evr": "2.7.5-3.el6",
            "group": "Development/Languages",
            "headeri18ntable": [
                "C"
            ],
            "license": "Python",
            "name": "python",
            "nevr": "python-2.7.5-3.el6",
            "nevra": "python-2.7.5-3.el6.x86_64",
            "nvr": "python-2.7.5-3.el6",
            "nvra": "python-2.7.5-3.el6.x86_64",
            "os": "linux",
            "release": "3.el6",
            "requires": [
                "autoconf",
                "bluez-libs-devel",
                "bzip2",
                "bzip2-devel",
                "expat-devel",
                "findutils",
                "gcc-c++",
                "gdbm-devel",
                "glibc-devel",
                "gmp-devel",
                "libdb-devel",
                "libffi-devel",
                "libGL-devel",
                "libX11-devel",
                "ncurses-devel",
                "openssl-devel",
                "pkgconfig",
                "readline-devel",
                "sqlite-devel",
                "systemtap-sdt-devel",
                "tar",
                "tcl-devel",
                "tix-devel",
                "tk-devel",
                "valgrind-devel",
                "zlib-devel"
            ],
            "summary": "An interpreted, interactive, object-oriented programming language",
            "url": "http://www.python.org/",
            "version": "2.7.5"
        },
        "path": "/home/harlowja/anvil/python.spec",
        "sources": [
            "05000-autotool-intermediates.patch",
            "00184-ctypes-should-build-with-libffi-multilib-wrapper.patch",
            "00181-allow-arbitrary-timeout-in-condition-wait.patch",
            "00180-python-add-support-for-ppc64p7.patch",
            ....
            "00055-systemtap.patch",
            "python-2.6.4-distutils-rpath.patch",
            "python-2.6-rpath.patch",
            "python-2.7rc1-socketmodule-constants2.patch",
            "python-2.7rc1-socketmodule-constants.patch",
            "python-2.7rc1-binutils-no-dep.patch",
            "python-2.5.1-sqlite-encoding.patch",
            "python-2.5.1-plural-fix.patch",
            "python-2.5-cflags.patch",
            "00001-pydocnogui.patch",
            "python-2.7.1-config.patch",
            "pynche",
            "macros.python2",
            "pyfuntop.stp",
            "systemtap-example.stp",
            "libpython.stp",
            "pythondeps.sh",
            "http://www.python.org/ftp/python/2.7.5/Python-2.7.5.tar.xz"
        ]
    }

`specprint` is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.


git-changelog
-------------
This tool generates a pretty software's changelog from git history.


build-install-node-from-source.sh
---------------------------------

Helps build latest `node.js` from source into rpms.


build-openvswitch.sh
--------------------

Helps build latest `openvswitch` from source into rpms.

clean-pip
---------

This utility removes package installed by pip but not by rpm.

clear-dns.sh
------------

Removes leftover nova dnsmasq processes frequently left behind.

img-uploader
------------

Helper tool to upload images to glance using your anvil settings.

validate-yaml
-------------

Validates a yaml file is formatted correctly.

yaml-pretty
-----------

Pretty prints yaml into a standard format.

resize.sh
---------

Resizes a images filesystem using guestfish.

euca.sh
-------

Creates ec2 keys for usage with nova.
