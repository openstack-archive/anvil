#!/usr/bin/env python
"""
This script bootstraps anvil with a pbr rpm for scl python27.
"""


import argparse
import atexit
import contextlib
import exceptions
import fnmatch
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib
import urlparse


DEFAULT_LOG_FORMAT = '%(asctime)s|%(levelname)s|%(name)s| %(message)s'
DEFAULT_LOG_LEVEL = logging.WARNING


def configure_logging(format=DEFAULT_LOG_FORMAT, level=DEFAULT_LOG_LEVEL,
                      **kwargs):
    """Configure application logging."""
    if 'verbose' in kwargs:
        level = logging.INFO if kwargs['verbose'] < 2 else logging.DEBUG
    logging.basicConfig(format=format, level=level, **kwargs)


def configure_argument_parser():
    """Configure application argument parsing."""
    parser = argparse.ArgumentParser(
        description='Build pbr rpm for python27 scl',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--pbr-url',
                        default=('https://pypi.python.org'
                                 '/packages/source/p/pbr/pbr-0.10.0.tar.gz'),
                        help='url of pbr package on pypi')
    default_rpm_fn = 'python27-python-pbr-0.10.0.noarch.rpm'
    parser.add_argument('--rpm-fn',
                        default=os.path.join(os.getcwd(), default_rpm_fn),
                        help='filename of output rpm')
    parser.add_argument('--pip-dirn',
                        default=mkdtemp_and_delete_atexit(),
                        help='directory to uncompress pbr package')
    parser.add_argument('--python',
                        default='python',
                        help='path to interpreter used to run setup.py')
    parser.add_argument('--spec2scl',
                        default='spec2scl',
                        help='path to spec2scl script')
    parser.add_argument('--rpmbuild',
                        default='rpmbuild',
                        help='path to rpmbuild script')
    parser.add_argument('--verbose', '-v', action='count')
    return parser


def mkdtemp_and_delete_atexit():
    """Create a temporary directory which deletes itself on program exit."""
    tmp_dirn = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, tmp_dirn)
    return tmp_dirn


def walk_and_fnmatch(root_dirn, file_pat, match_dirnames=False):
    """Find all files matching pattern from the top of directory tree."""
    matches = []
    for root, dirnames, filenames in os.walk(root_dirn):
        names = filenames
        if match_dirnames:
            names.extend(dirnames)
        for filename in fnmatch.filter(names, file_pat):
            matches.append(os.path.join(root, filename))
    return matches


def walk_and_chown(root_dirn, uid=os.getuid(), gid=os.getgid()):
    """Do equivalent of chown -R and chgrp -R on a directory tree."""
    for root, dirnames, filenames in os.walk(root_dirn):
        for dirn in dirnames:
            os.chown(os.path.join(root, dirn), uid, gid)
        for fn in filenames:
            os.chown(os.path.join(root, fn), uid, gid)


def install_dependencies():
    """Install dependencies required for building scl rpm."""
    subprocess.check_call(args=['sudo', 'yum', 'install', '-y',
                                'python27-build', 'python27-scldevel',
                                'scl-utils', 'scl-utils-build', 'spec2scl'])


def main(**kwargs):
    pbr_url = kwargs.pop('pbr_url')
    pip_dirn = kwargs.pop('pip_dirn')

    # Download pbr tgz file from pypi.
    pbr_tgz_fn = os.path.join(pip_dirn, os.path.basename(
                              urlparse.urlparse(pbr_url).path))
    logging.debug('downloading pbr url {0} to {1}'.format(pbr_url, pbr_tgz_fn))
    urllib.urlretrieve(url=pbr_url, filename=pbr_tgz_fn)
    with contextlib.closing(tarfile.open(name=pbr_tgz_fn,
                                         mode='r:gz')) as tar_fh:

        # Uncompress the tgz file.
        logging.debug('extracting pbr in {0}'.format(pip_dirn))
        tar_fh.extractall(path=pip_dirn)
        base_dirn = os.path.dirname(pbr_tgz_fn)
        pbr_tgz_basen = os.path.basename(pbr_tgz_fn).rstrip('.tar.gz')
        pbr_tgz_dirn = os.path.join(base_dirn, pbr_tgz_basen)
        walk_and_chown(pbr_tgz_dirn)  # sadly, sometimes needed

        # Build a spec file and package for rpm.
        os.chdir(pbr_tgz_dirn)
        logging.debug('building with setuptools in {0}'.format(pbr_tgz_dirn))
        setup_fn = os.path.join(pbr_tgz_dirn, 'setup.py')
        subprocess.check_call(args=[kwargs['python'], setup_fn, 'bdist_rpm'])

        # Make the spec file scl ready.
        spec_matches = walk_and_fnmatch(pbr_tgz_dirn, 'pbr.spec')
        if len(spec_matches) != 1:
            raise exceptions.AssertionError('expected exactly one spec file')
        spec_fn = spec_matches[0]
        logging.debug('making spec file scl ready {0}'.format(spec_fn))
        subprocess.check_call(args=[kwargs['spec2scl'], '-m', '-i',
                              spec_fn])
        subprocess.check_call(args=['sed', '--in-place',
                              's/^%define name pbr/%define name python\-pbr/',
                                    spec_fn])

        # Rename the tgz created for rpm to match rpm name.
        build_dirn = os.path.join(pbr_tgz_dirn, 'build')
        tgz_matches = walk_and_fnmatch(build_dirn,
                                       '{0}.tar.gz'.format(pbr_tgz_basen))
        if len(tgz_matches) != 1:
            raise exceptions.AssertionError('expected one build tar.gz')
        build_tgz_fn = tgz_matches[0]
        logging.debug('renaming tgz to match rpm {0}'.format(build_tgz_fn))
        build_tgz_dirn = os.path.dirname(build_tgz_fn)
        os.chdir(build_tgz_dirn)
        # Uncompress and delete the tgz with pypi name.
        with contextlib.closing(tarfile.open(name=build_tgz_fn,
                                             mode='r:gz')) as build_tar_fh:
            build_tar_fh.extractall(path=build_tgz_dirn)
        os.unlink(build_tgz_fn)
        # Create a new tgz which matches rpm name.
        old_build_tgz_dirn = os.path.basename(build_tgz_fn).rstrip('.tar.gz')
        new_build_tgz_dirn = 'python27-python-{0}'.format(old_build_tgz_dirn)
        os.rename(old_build_tgz_dirn, new_build_tgz_dirn)
        new_build_tgz_fn = '{0}.tar.gz'.format(new_build_tgz_dirn)
        with contextlib.closing(tarfile.open(name=new_build_tgz_fn,
                                             mode='w:gz')) as build_tar_fh:
            build_tar_fh.add(new_build_tgz_dirn)
        shutil.rmtree(new_build_tgz_dirn)

        # Build the rpm.
        logging.debug('building rpm from spec file {0}'.format(spec_fn))
        top_dirn_matches = walk_and_fnmatch(build_dirn, 'rpm',
                                            match_dirnames=True)
        if len(top_dirn_matches) != 1:
            raise exceptions.AssertionError('expected one top dir in build')
        top_dirn = top_dirn_matches[0]
        os.chdir(pbr_tgz_dirn)
        # Note: subprocess module was doing weird things passing arguments
        # containing white spaces as a list, so I am using a string and
        # passing to shell, both of which are required for this to work.
        cmdstr = "{0} -ba {1} -D 'scl python27' -D '_topdir {2}'".format(
                 kwargs['rpmbuild'], spec_fn, top_dirn)
        logging.debug('executing cmd {0}'.format(cmdstr))
        subprocess.check_call(args=cmdstr, shell=True)

        # Copy the rpm
        rpm_matches = walk_and_fnmatch(build_dirn,
                                       'python27-python-pbr-*.noarch.rpm')
        if len(rpm_matches) != 1:
            raise exceptions.AssertionError('expected one matching rpm')
        rpm_fn = rpm_matches[0]
        logging.debug('copying rpm from {0} to {1}'.format(rpm_fn,
                                                           kwargs['rpm_fn']))
        shutil.copy(rpm_fn, kwargs['rpm_fn'])


if __name__ == '__main__':
    parser = configure_argument_parser()
    args = parser.parse_args()
    opts = vars(args)  # return args.__dict__
    configure_logging(**opts)
    install_dependencies()
    main(**opts)
