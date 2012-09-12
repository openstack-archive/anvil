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

import contextlib
import os
import re
import tarfile
import urlparse

from anvil import colorizer
from anvil import downloader as down
from anvil import importer
from anvil import log
from anvil import shell as sh
from anvil import utils

LOG = log.getLogger(__name__)

# Extensions that tarfile knows how to work with
TAR_EXTS = ['.tgz', '.gzip', '.gz', '.bz2', '.tar']

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
    re.compile(r"(.*)qcow2$", re.I),
    re.compile(r'(.*?)aki-tty/image$', re.I),
]

# Used to match various file names with what could be a ram disk image
RAMDISK_CHECKS = [
    re.compile(r"(.*)-initrd$", re.I),
    re.compile(r"(.*)initramfs(.*)$", re.I),
    re.compile(r'(.*?)ari-tty/image$', re.I),
]

# Skip files that match these patterns
SKIP_CHECKS = [
    re.compile(r"^[.]", re.I),
]

# File extensions we will skip over (typically of content hashes)
BAD_EXTENSIONS = ['md5', 'sha', 'sfv']


class Unpacker(object):

    def _get_tar_file_members(self, arc_fn):
        LOG.info("Finding what exists in %s.", colorizer.quote(arc_fn))
        files = []
        with contextlib.closing(tarfile.open(arc_fn, 'r')) as tfh:
            for tmemb in tfh.getmembers():
                if not tmemb.isfile():
                    continue
                fn = tmemb.name
                files.append(fn)
        return files

    def _pat_checker(self, fn, patterns):
        (root_fn, fn_ext) = os.path.splitext(fn)
        if utils.has_any(fn_ext.lower(), *BAD_EXTENSIONS):
            return False
        for pat in patterns:
            if pat.match(fn):
                return True
        return False

    def _find_pieces(self, files, files_location):
        """
        Match files against the patterns in KERNEL_CHECKS,
        RAMDISK_CHECKS, and ROOT_CHECKS to determine which files
        contain which image parts.
        """
        kernel_fn = None
        ramdisk_fn = None
        img_fn = None
        utils.log_iterable(files, logger=LOG,
              header="Looking at %s files from %s to find the kernel/ramdisk/root images" % (len(files), colorizer.quote(files_location)))

        for fn in files:
            if self._pat_checker(fn, KERNEL_CHECKS):
                kernel_fn = fn
                LOG.debug("Found kernel: %r" % (fn))
            elif self._pat_checker(fn, RAMDISK_CHECKS):
                ramdisk_fn = fn
                LOG.debug("Found ram disk: %r" % (fn))
            elif self._pat_checker(fn, ROOT_CHECKS):
                img_fn = fn
                LOG.debug("Found root image: %r" % (fn))
            else:
                LOG.debug("Unknown member %r - skipping" % (fn))

        return (img_fn, ramdisk_fn, kernel_fn)

    def _unpack_tar_member(self, tarhandle, member, output_location):
        LOG.info("Extracting %s to %s.", colorizer.quote(member.name), colorizer.quote(output_location))
        with contextlib.closing(tarhandle.extractfile(member)) as mfh:
            with open(output_location, "wb") as ofh:
                return sh.pipe_in_out(mfh, ofh)

    def _describe(self, root_fn, ramdisk_fn, kernel_fn):
        """
        Make an "info" dict that describes the path, disk format, and
        container format of each component of an image.
        """
        info = dict()
        if kernel_fn:
            info['kernel'] = {
                'file_name': kernel_fn,
                'disk_format': 'aki',
                'container_format': 'aki',
            }
        if ramdisk_fn:
            info['ramdisk'] = {
                'file_name': ramdisk_fn,
                'disk_format': 'ari',
                'container_format': 'ari',
            }
        info['file_name'] = root_fn
        info['disk_format'] = 'ami'
        info['container_format'] = 'ami'
        return info

    def _filter_files(self, files):
        filtered = []
        for fn in files:
            if self._pat_checker(fn, SKIP_CHECKS):
                pass
            else:
                filtered.append(fn)
        return filtered

    def _unpack_tar(self, file_name, file_location, tmp_dir):
        (root_name, _) = os.path.splitext(file_name)
        tar_members = self._filter_files(self._get_tar_file_members(file_location))
        (root_img_fn, ramdisk_fn, kernel_fn) = self._find_pieces(tar_members, file_location)
        if not root_img_fn:
            msg = "Tar file %r has no root image member" % (file_name)
            raise IOError(msg)
        kernel_real_fn = None
        root_real_fn = None
        ramdisk_real_fn = None
        self._log_pieces_found('archive', root_img_fn, ramdisk_fn, kernel_fn)
        extract_dir = sh.mkdir(sh.joinpths(tmp_dir, root_name))
        with contextlib.closing(tarfile.open(file_location, 'r')) as tfh:
            for m in tfh.getmembers():
                if m.name == root_img_fn:
                    root_real_fn = sh.joinpths(extract_dir, sh.basename(root_img_fn))
                    self._unpack_tar_member(tfh, m, root_real_fn)
                elif ramdisk_fn and m.name == ramdisk_fn:
                    ramdisk_real_fn = sh.joinpths(extract_dir, sh.basename(ramdisk_fn))
                    self._unpack_tar_member(tfh, m, ramdisk_real_fn)
                elif kernel_fn and m.name == kernel_fn:
                    kernel_real_fn = sh.joinpths(extract_dir, sh.basename(kernel_fn))
                    self._unpack_tar_member(tfh, m, kernel_real_fn)
        return self._describe(root_real_fn, ramdisk_real_fn, kernel_real_fn)

    def _log_pieces_found(self, src_type, root_fn, ramdisk_fn, kernel_fn):
        pieces = []
        if root_fn:
            pieces.append("%s (root image)" % (colorizer.quote(root_fn)))
        if ramdisk_fn:
            pieces.append("%s (ramdisk image)" % (colorizer.quote(ramdisk_fn)))
        if kernel_fn:
            pieces.append("%s (kernel image)" % (colorizer.quote(kernel_fn)))
        if pieces:
            utils.log_iterable(pieces, logger=LOG,
                                header="Found %s images from a %s" % (len(pieces), src_type))

    def _unpack_dir(self, dir_path):
        """
        Pick through a directory to figure out which files are which
        image pieces, and create a dict that describes them.
        """
        potential_files = set()
        for fn in self._filter_files(sh.listdir(dir_path)):
            full_fn = sh.joinpths(dir_path, fn)
            if sh.isfile(full_fn):
                potential_files.add(sh.canon_path(full_fn))
        (root_fn, ramdisk_fn, kernel_fn) = self._find_pieces(potential_files, dir_path)
        if not root_fn:
            msg = "Directory %r has no root image member" % (dir_path)
            raise IOError(msg)
        self._log_pieces_found('directory', root_fn, ramdisk_fn, kernel_fn)
        return self._describe(root_fn, ramdisk_fn, kernel_fn)

    def unpack(self, file_name, file_location, tmp_dir):
        if sh.isdir(file_location):
            return self._unpack_dir(file_location)
        elif sh.isfile(file_location):
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
        msg = "Currently we do not know how to unpack %r" % (file_location)
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
        self.parsed_url = urlparse.urlparse(url)

    def _check_name(self, name):
        LOG.info("Checking if image %s already exists already in glance.", colorizer.quote(name))
        if name in self.registry:
            raise IOError("Image named %s already exists." % (name))

    def _register(self, image_name, location):

        # Upload the kernel, if we have one
        kernel = location.pop('kernel', None)
        kernel_id = ''
        if kernel:
            kernel_image_name = "%s-vmlinuz" % (image_name)
            self._check_name(kernel_image_name)
            LOG.info('Adding kernel %s to glance.', colorizer.quote(kernel_image_name))
            LOG.info("Please wait installing...")
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
            LOG.info('Adding ramdisk %s to glance.', colorizer.quote(ram_image_name))
            LOG.info("Please wait installing...")
            with open(initrd['file_name'], 'r') as fh:
                resource = self.client.images.create(data=fh,
                    container_format=initrd['container_format'],
                    disk_format=initrd['disk_format'],
                    name=ram_image_name)
                initrd_id = resource.id

        # Upload the root, we must have one...
        LOG.info('Adding image %s to glance.', colorizer.quote(image_name))
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
        LOG.info("Please wait installing...")
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
        return sh.basename(self.parsed_url.path)

    def _is_url_local(self):
        return (sh.exists(self.url) or (self.parsed_url.scheme == '' and self.parsed_url.netloc == ''))

    def install(self):
        url_fn = self._extract_url_fn()
        if not url_fn:
            raise IOError("Can not determine file name from url: %r" % (self.url))
        with utils.tempdir() as tdir:
            if not self._is_url_local():
                (fetched_fn, bytes_down) = down.UrlLibDownloader(self.url, sh.joinpths(tdir, url_fn)).download()
                LOG.debug("For url %s we downloaded %s bytes to %s", self.url, bytes_down, fetched_fn)
            else:
                fetched_fn = self.url
            unpack_info = Unpacker().unpack(url_fn, fetched_fn, tdir)
            tgt_image_name = self._generate_img_name(url_fn)
            img_id = self._register(tgt_image_name, unpack_info)
            return (tgt_image_name, img_id)


class UploadService(object):

    def __init__(self, params):
        self.params = params

    def _get_token(self, kclient_v2):
        LOG.info("Getting your keystone token so that image uploads may proceed.")
        params = self.params['keystone']
        client = kclient_v2.Client(username=params['demo_user'],
            password=params['demo_password'],
            tenant_name=params['demo_tenant'],
            auth_url=params['endpoints']['public']['uri'])
        return client.auth_token

    def install(self, urls):
        am_installed = 0
        try:
            gclient_v1 = importer.import_module('glanceclient.v1.client')
            gexceptions = importer.import_module('glanceclient.common.exceptions')
            kclient_v2 = importer.import_module('keystoneclient.v2_0.client')
            kexceptions = importer.import_module('keystoneclient.exceptions')
        except RuntimeError as e:
            LOG.exception("Failed at importing required client modules: %s", e)
            return am_installed
        if urls:
            try:
                # Ensure all services ok
                for n in ['glance', 'keystone']:
                    params = self.params[n]
                    utils.wait_for_url(params['endpoints']['public']['uri'])
                params = self.params['glance']
                client = gclient_v1.Client(endpoint=params['endpoints']['public']['uri'],
                                           token=self._get_token(kclient_v2))
            except (RuntimeError, gexceptions.ClientException,
                    kexceptions.ClientException, IOError) as e:
                LOG.exception('Failed fetching needed clients for image calls due to: %s', e)
                return am_installed
            utils.log_iterable(urls, logger=LOG,
                                header="Attempting to download+extract+upload %s images" % len(urls))
            for url in urls:
                try:
                    (name, img_id) = Image(client, url).install()
                    LOG.info("Installed image named %s with image id %s.", colorizer.quote(name), colorizer.quote(img_id))
                    am_installed += 1
                except (IOError,
                        tarfile.TarError,
                        gexceptions.ClientException,
                        kexceptions.ClientException) as e:
                    LOG.exception('Installing %r failed due to: %s', url, e)
        return am_installed


def get_shared_params(ip, api_port=9292, protocol='http', reg_port=9191, **kwargs):
    mp = {}
    mp['service_host'] = ip

    glance_host = ip
    glance_port = api_port
    glance_protocol = protocol
    glance_registry_port = reg_port

    # Uri's of the http/https endpoints
    mp['endpoints'] = {
        'admin': {
            'uri': utils.make_url(glance_protocol, glance_host, glance_port),
            'port': glance_port,
            'host': glance_host,
            'protocol': glance_protocol,
        },
        'registry': {
            'uri': utils.make_url(glance_protocol, glance_host, glance_registry_port),
            'port': glance_registry_port,
            'host': glance_host,
            'protocol': glance_protocol,
        }
    }
    mp['endpoints']['internal'] = dict(mp['endpoints']['admin'])
    mp['endpoints']['public'] = dict(mp['endpoints']['admin'])
    return mp
