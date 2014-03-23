#!/usr/bin/env python

from setuptools import setup, find_packages


def read_requires(filename):
    requires = []
    with open(filename, "rb") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            requires.append(line)
    return requires


setup(name='anvil',
      description='A tool to forge raw OpenStack into a productive tool',
      author='OpenStack Foundation',
      author_email='anvil-dev@lists.launchpad.net',
      url='http://anvil.readthedocs.org/',
      long_description=open("README.rst", 'rb').read(),
      packages=find_packages(),
      license='Apache Software License',
      scripts=[
        "tools/yyoom",
        "tools/py2rpm",
        "tools/multipip",
        "tools/specprint",
      ],
      install_requires=read_requires("requirements.txt"),
      tests_require=read_requires("test-requirements.txt"),
      classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Environment :: OpenStack',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
      ],
     )
