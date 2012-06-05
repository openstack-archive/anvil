# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
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

from optparse import OptionParser, OptionGroup

import contextlib
import getpass
import os
import re
import shutil
import sys
import tarfile
import tempfile
import urllib2
import urlparse

import logging

import glanceclient.common.exceptions as gexceptions
import glanceclient.v1.client as gclient_v1
import keystoneclient.exceptions as kexceptions
import keystoneclient.v2_0.client as kclient_v2

# Extensions that tarfile knows how to work with
TAR_EXTS = ['.tgz', '.gzip', '.gz', '.bz2', '.tar']

# 1KB at a time
DOWNLOAD_CHUNK_SIZE = 1024

# Used to attempt to produce a name for images (to see if we already have it)
# And to use as the final name...
# Reverse sorted so that .tar.gz replaces before .tar (and so on)
NAME_CLEANUPS = [
    '.tar.gz',
    '.img.gz',
    '.qcow2',
    '.img',
] + TAR_EXTS
NAME_CLEANUPS.sort()
NAME_CLEANUPS.reverse()

# Used to match various file names with what could be a kernel image
KERNEL_CHECKS = [
    re.compile(r"(.*)vmlinuz(.*)$", re.I),
    re.compile(r'(.*?)aki-tty/image$', re.I),
]

# Used to match various file names with what could be a root image
ROOT_CHECKS = [
    re.compile(r"(.*)img$", re.I),
    re.compile(r'(.*?)aki-tty/image$', re.I),
]

# Used to match various file names with what could be a ram disk image
RAMDISK_CHECKS = [
    re.compile(r"(.*)-initrd$", re.I),
    re.compile(r"(.*)initramfs(.*)$", re.I),
    re.compile(r'(.*?)ari-tty/image$', re.I),
]


@contextlib.contextmanager
def tempdir(**kwargs):
    # This seems like it was only added in python 3.2
    # Make it since its useful...
    # See: http://bugs.python.org/file12970/tempdir.patch
    tdir = tempfile.mkdtemp(**kwargs)
    try:
        yield tdir
    finally:
        shutil.rmtree(tdir)


def pipe_in_out(in_fh, out_fh, chunk_size=1024):
    bytes_piped = 0
    while True:
        data = in_fh.read(chunk_size)
        if data == '':
            break
        else:
            ofh.write(data)
            bytes_piped += len(data)
    return bytes_piped


class UrlLibDownloader(object):

    def __init__(self, uri, store_where, **kargs):
        self.uri = uri
        self.store_where = store_where
        self.timeout = int(kargs.get('timeout', 5))

    def download(self):
        print('Downloading using urllib2: %s to %s.' % (self.uri, self.store_where))
        with contextlib.closing(urllib2.urlopen(self.uri, timeout=self.timeout)) as conn:
            c_len = conn.headers.get('content-length')
            try:
                c_len = int(c_len)
            except ValueError:
                c_len = None
            if c_len is not None:
                print("Downloading %s bytes." % (c_len))
            with open(self.store_where, 'wb') as ofh:
                return pipe_in_out(conn, ofh, DOWNLOAD_CHUNK_SIZE)


class Unpacker(object):

    def _find_pieces(self, arc_fn):
        kernel_fn = None
        ramdisk_fn = None
        img_fn = None

        print("Peeking into %s to find its kernel/ramdisk/root images." % (arc_fn))

        def pat_checker(fn, patterns):
            for pat in patterns:
                if pat.match(fn):
                    return True
            return False

        with contextlib.closing(tarfile.open(arc_fn, 'r')) as tfh:
            for tmemb in tfh.getmembers():
                if not tmemb.isfile():
                    continue
                fn = tmemb.name
                if pat_checker(fn, KERNEL_CHECKS):
                    kernel_fn = fn
                    print("Found kernel: %r" % (fn))
                elif pat_checker(fn, RAMDISK_CHECKS):
                    ramdisk_fn = fn
                    print("Found ram disk: %r" % (fn))
                elif pat_checker(fn, ROOT_CHECKS):
                    img_fn = fn
                    print("Found root image: %r" % (fn))
                else:
                    print("Unknown member %r - skipping" % (fn))

        return (img_fn, ramdisk_fn, kernel_fn)

    def _unpack_tar_member(self, tarhandle, member, output_location):
        print("Extracting %s to %s." % (member.name, output_location))
        bytes_written = 0
        with contextlib.closing(tarhandle.extractfile(member)) as mfh:
            with open(output_location, "wb") as ofh:
                blob = mfh.read(8192)
                while blob != '':
                    ofh.write(blob)
                    bytes_written += len(blob)
                    blob = mfh.read(8192)
        return bytes_written

    def _unpack_tar(self, file_name, file_location, tmp_dir):
        (root_name, _) = os.path.splitext(file_name)
        (root_img_fn, ramdisk_fn, kernel_fn) = self._find_pieces(file_location)
        if not root_img_fn:
            msg = "Image %r has no root image member" % (file_name)
            raise IOError(msg)
        extract_dir = os.path.join(tmp_dir, root_name)
        os.makedirs(extract_dir)
        kernel_real_fn = None
        root_real_fn = None
        ramdisk_real_fn = None
        with contextlib.closing(tarfile.open(file_location, 'r')) as tfh:
            for m in tfh.getmembers():
                if m.name == root_img_fn:
                    root_real_fn = os.path.join(extract_dir, os.path.basename(root_img_fn))
                    self._unpack_tar_member(tfh, m, root_real_fn)
                elif ramdisk_fn and m.name == ramdisk_fn:
                    ramdisk_real_fn = os.path.join(extract_dir, os.path.basename(ramdisk_fn))
                    self._unpack_tar_member(tfh, m, ramdisk_real_fn)
                elif kernel_fn and m.name == kernel_fn:
                    kernel_real_fn = os.path.join(extract_dir, os.path.basename(kernel_fn))
                    self._unpack_tar_member(tfh, m, kernel_real_fn)
        info = dict()
        if kernel_real_fn:
            info['kernel'] = {
                'file_name': kernel_real_fn,
                'disk_format': 'aki',
                'container_format': 'aki',
            }
        if ramdisk_real_fn:
            info['ramdisk'] = {
                'file_name': ramdisk_real_fn,
                'disk_format': 'ari',
                'container_format': 'ari',
            }
        info['file_name'] = root_real_fn
        info['disk_format'] = 'ami'
        info['container_format'] = 'ami'
        return info

    def unpack(self, file_name, file_location, tmp_dir):
        (_, fn_ext) = os.path.splitext(file_name)
        fn_ext = fn_ext.lower()
        if fn_ext in TAR_EXTS:
            return self._unpack_tar(file_name, file_location, tmp_dir)
        elif fn_ext in ['.img', '.qcow2']:
            info = dict()
            info['file_name'] = file_location
            if fn_ext == '.img':
                info['disk_format'] = 'raw'
            else:
                info['disk_format'] = 'qcow2'
            info['container_format'] = 'bare'
            return info
        else:
            msg = "Currently we do not know how to unpack %r" % (file_name)
            raise IOError(msg)


class Registry(object):
    def __init__(self, client):
        self.client = client

    def _extract_names(self):
        names = dict()
        images = self.client.images.list()
        for image in images:
            name = image.name
            names[name] = image.id
        return names

    def __contains__(self, name):
        names = self._extract_names()
        if name in names:
            return True
        else:
            return False


class Image(object):

    def __init__(self, client, url):
        self.client = client
        self.registry = Registry(client)
        self.url = url

    def _check_name(self, name):
        print("Checking if image %s already exists already in glance." % (name))
        if name in self.registry:
            raise IOError("Image named %s already exists." % (name))

    def _register(self, image_name, location):

        # Upload the kernel, if we have one
        kernel = location.pop('kernel', None)
        kernel_id = ''
        if kernel:
            kernel_image_name = "%s-vmlinuz" % (image_name)
            self._check_name(kernel_image_name)
            print('Adding kernel %s to glance.' % (kernel_image_name))
            print("Please wait installing...")
            with open(kernel['file_name'], 'r') as fh:
                resource = self.client.images.create(data=fh,
                    container_format=kernel['container_format'],
                    disk_format=kernel['disk_format'],
                    name=kernel_image_name)
                kernel_id = resource.id

        # Upload the ramdisk, if we have one
        initrd = location.pop('ramdisk', None)
        initrd_id = ''
        if initrd:
            ram_image_name = "%s-initrd" % (image_name)
            self._check_name(ram_image_name)
            print('Adding ramdisk %s to glance.' % (ram_image_name))
            print("Please wait installing...")
            with open(initrd['file_name'], 'r') as fh:
                resource = self.client.images.create(data=fh,
                    container_format=initrd['container_format'],
                    disk_format=initrd['disk_format'],
                    name=ram_image_name)
                initrd_id = resource.id

        # Upload the root, we must have one...
        print('Adding image %s to glance.' % (image_name))
        self._check_name(image_name)
        args = dict()
        args['name'] = image_name
        if kernel_id or initrd_id:
            args['properties'] = dict()
            if kernel_id:
                args['properties']['kernel_id'] = kernel_id
            if initrd_id:
                args['properties']['ramdisk_id'] = initrd_id
        args['container_format'] = location['container_format']
        args['disk_format'] = location['disk_format']
        print("Please wait installing...")
        with open(location['file_name'], 'r') as fh:
            resource = self.client.images.create(data=fh, **args)
            img_id = resource.id

        return img_id

    def _generate_img_name(self, url_fn):
        name = url_fn
        for look_for in NAME_CLEANUPS:
            name = name.replace(look_for, '')
        return name

    def _extract_url_fn(self):
        pieces = urlparse.urlparse(self.url)
        return os.path.basename(pieces.path)

    def install(self, tmp_path="/tmp"):
        url_fn = self._extract_url_fn()
        if not url_fn:
            raise IOError("Can not determine file name from url: %r" % (self.url))
        with tempdir(dir=tmp_path) as tdir:
            fetch_fn = os.path.join(tdir, url_fn)
            downloader = UrlLibDownloader(self.url, fetch_fn)
            bytes_down = downloader.download()
            print("Downloaded %s bytes to %s" % (bytes_down, fetch_fn))
            unpack_info = Unpacker().unpack(url_fn, fetch_fn, tdir)
            tgt_image_name = self._generate_img_name(url_fn)
            img_id = self._register(tgt_image_name, unpack_info)
            return (tgt_image_name, img_id)


class UploadService:

    def __init__(self, params):
        self.params = params

    def _get_token(self, kclient_v2):
        print("Getting your keystone token so that image uploads may proceed.")
        params = self.params
        client = kclient_v2.Client(username=params['user'],
            password=params['password'],
            tenant_name=params['tenant'],
            auth_url=params['keystone_uri'])
        return client.auth_token

    def install(self, urls):
        am_installed = 0
        if urls:
            try:
                params = self.params
                client = gclient_v1.Client(endpoint=params['glance_uri'],
                                           token=self._get_token(kclient_v2))
            except (RuntimeError, gexceptions.ClientException,
                    kexceptions.ClientException) as e:
                print('Failed fetching needed clients for image calls due to: %s' % (e))
                return am_installed
            for url in urls:
                try:
                    (name, img_id) = Image(client, url).install()
                    print("Installed image named %s with image id %s." % (name, img_id))
                    am_installed += 1
                except (IOError,
                        tarfile.TarError,
                        gexceptions.ClientException,
                        kexceptions.ClientException) as e:
                    print('Installing %r failed due to: %s' % (url, e))
        return am_installed


def setup_logging(vb, format='%(levelname)s: @%(name)s : %(message)s'):
    root_logger = logging.getLogger()
    console_logger = logging.StreamHandler(sys.stdout)
    console_logger.setFormatter(logging.Formatter(format))
    root_logger.addHandler(console_logger)
    root_logger.setLevel(logging.FATAL)
    if vb:
        root_logger.setLevel(logging.DEBUG)
        g_logger = logging.getLogger("glanceclient")
        g_logger.setLevel(logging.DEBUG)
        k_logger = logging.getLogger("keystoneclient")
        k_logger.setLevel(logging.DEBUG)


def password(prompt):
    result = ''
    while True:
        result = getpass.getpass(prompt)
        result = result.strip()
        if len(result) == 0:
            print("Please enter a non-blank password!")
        else:
            break
    return result


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("--upload",
        action="append",
        dest="urls",
        metavar="URL",
        help="URL to download and extract and upload")
    parser.add_option("--user",
        action="store",
        dest="user",
        metavar="USER",
        help="username to upload as")
    parser.add_option("-t", "--tenant",
        action="store",
        dest="tenant",
        metavar="TENANT",
        help="tenant to upload as")
    parser.add_option("-g", "--glance",
        action="store",
        dest="glance",
        metavar="URI",
        help="glance public uri")
    parser.add_option("-k", "--keystone",
        action="store",
        dest="keystone",
        metavar="URI",
        help="keystone public uri")
    parser.add_option("-v", "--verbose",
                  action="append_const", const=1, dest="verbosity", default=[1],
                  help="increase the verbose level")
    (options, args) = parser.parse_args()
    if not options.user:
        parser.error("No username provided")
    if not options.tenant:
        parser.error("No tenant name provided")
    if not options.glance:
        parser.error("No glance uri provided")
    if not options.keystone:
        parser.error("No keystone uri provided")
    urls = options.urls or []
    if not urls:
        parser.error("No urls provided")
    setup_logging(len(options.verbosity) > 1)
    pw = password("Password for user %r: " % (options.user))
    params = {
        'user': options.user,
        'tenant': options.tenant,
        'glance_uri': options.glance,
        'keystone_uri': options.keystone,
        'password': pw,
    }
    am_installed = UploadService(params).install(urls)
    if am_installed != len(urls):
        sys.exit(1)
    else:
        sys.exit(0)
