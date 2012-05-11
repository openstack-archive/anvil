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


class Unpacker(object):

    def _find_pieces(self, arc_fn):
        kernel_fn = None
        ramdisk_fn = None
        img_fn = None

        LOG.info("Peeking into %s to find its kernel/ramdisk/root images.", colorizer.quote(arc_fn))

        def is_kernel(fn):
            return re.match(r"(.*)-vmlinuz(.*)$", fn, re.I) or re.match(r'(.*?)aki-tty/image$', fn, re.I)

        def is_root(fn):
            return re.match(r"(.*)img$", fn, re.I) or re.match(r'(.*?)ami-tty/image$', fn, re.I)

        def is_ramdisk(fn):
            return re.match(r"(.*)-initrd$", fn, re.I) or re.match(r'(.*?)ari-tty/image$', fn, re.I)

        with contextlib.closing(tarfile.open(arc_fn, 'r')) as tfh:
            for tmemb in tfh.getmembers():
                fn = tmemb.name
                if is_kernel(fn):
                    kernel_fn = fn
                    LOG.debug("Found kernel: %r" % (fn))
                elif is_ramdisk(fn):
                    ramdisk_fn = fn
                    LOG.debug("Found ram disk: %r" % (fn))
                elif is_root(fn):
                    img_fn = fn
                    LOG.debug("Found root image: %r" % (fn))
                else:
                    LOG.debug("Unknown member %r - skipping" % (fn))
        return (img_fn, ramdisk_fn, kernel_fn)

    def _unpack_tar(self, file_name, file_location, tmp_dir):
        (root_name, _) = os.path.splitext(file_name)
        (root_img_fn, ramdisk_fn, kernel_fn) = self._find_pieces(file_location)
        if not root_img_fn:
            msg = "Image %r has no root image member" % (file_name)
            raise IOError(msg)
        extract_dir = sh.joinpths(tmp_dir, root_name)
        sh.mkdir(extract_dir)
        LOG.info("Extracting %s to %s", colorizer.quote(file_location), colorizer.quote(extract_dir))
        with contextlib.closing(tarfile.open(file_location, 'r')) as tfh:
            tfh.extractall(extract_dir)
        info = dict()
        if kernel_fn:
            info['kernel'] = {
                'file_name': sh.joinpths(extract_dir, kernel_fn),
                'disk_format': 'aki',
                'container_format': 'aki',
            }
        if ramdisk_fn:
            info['ramdisk'] = {
                'file_name': sh.joinpths(extract_dir, ramdisk_fn),
                'disk_format': 'ari',
                'container_format': 'ari',
            }
        info['file_name'] = sh.joinpths(extract_dir, root_img_fn)
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
        pieces = urlparse.urlparse(self.url)
        return sh.basename(pieces.path)

    def install(self):
        url_fn = self._extract_url_fn()
        if not url_fn:
            raise IOError("Can not determine file name from url: %r" % (self.url))
        with utils.tempdir() as tdir:
            fetch_fn = sh.joinpths(tdir, url_fn)
            down.UrlLibDownloader(self.url, fetch_fn).download()
            unpack_info = Unpacker().unpack(url_fn, fetch_fn, tdir)
            tgt_image_name = self._generate_img_name(url_fn)
            img_id = self._register(tgt_image_name, unpack_info)
            return (tgt_image_name, img_id)


class UploadService:

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
            LOG.exeception("Failed at importing required client modules: %s", e)
            return am_installed
        if urls:
            try:
                params = self.params['glance']
                client = gclient_v1.Client(endpoint=params['endpoints']['public']['uri'],
                                           token=self._get_token(kclient_v2))
            except (RuntimeError, gexceptions.ClientException,
                    kexceptions.ClientException) as e:
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


def get_shared_params(cfg):
    mp = dict()

    host_ip = cfg.get('host', 'ip')
    mp['service_host'] = host_ip

    glance_host = cfg.getdefaulted('glance', 'glance_host', host_ip)
    glance_port = cfg.getdefaulted('glance', 'glance_port', '9292')
    glance_protocol = cfg.getdefaulted('glance', 'glance_protocol', 'http')

    # Registry should be on the same host
    glance_registry_port = cfg.getdefaulted('glance', 'glance_registry_port', '9191')

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

    LOG.debug("Glance shared params: %s", mp)
    return mp
