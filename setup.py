#!/usr/bin/env python

#    Copyright (C) 2014 Yahoo! Inc. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import setuptools

from anvil import version


def read_requires(filename):
    requires = []
    with open(filename, "rb") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            requires.append(line)
    return requires


setuptools.setup(
    name='anvil',
    description='A tool to forge raw OpenStack into a productive tool',
    author='OpenStack Foundation',
    author_email='anvil-dev@lists.launchpad.net',
    url='http://anvil.readthedocs.org/',
    long_description=open("README.rst", 'rb').read(),
    packages=setuptools.find_packages(),
    license='Apache Software License',
    version=version.version_string(),
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
