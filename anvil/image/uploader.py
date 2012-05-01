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
from anvil import log
from anvil import shell as sh
from anvil import utils

LOG = log.getLogger(__name__)

# Glance client commands
IMAGE_ADD = ['glance',
             '--os-image-url', '%GLANCE_HOSTPORT%',
             '--os-username', '%DEMO_USER_NAME%',
             '--os-tenant-name', '%DEMO_TENANT_NAME%',
             '--os-auth-url', '%SERVICE_ENDPOINT%',
             'image-create',
             '--name', '%NAME%',
             '--public',
             '--container-format', '%CONTAINER_FORMAT%',
             '--disk-format', '%DISK_FORMAT%']

IMAGE_LIST = ['glance',
             '--os-image-url', '%GLANCE_HOSTPORT%',
             '--os-username', '%DEMO_USER_NAME%',
             '--os-tenant-name', '%DEMO_TENANT_NAME%',
             '--os-auth-url', '%SERVICE_ENDPOINT%',
             'image-list']

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
                'FILE_NAME': sh.joinpths(extract_dir, kernel_fn),
                'DISK_FORMAT': 'aki',
                'CONTAINER_FORMAT': 'aki',
            }
        if ramdisk_fn:
            info['ramdisk'] = {
                'FILE_NAME': sh.joinpths(extract_dir, ramdisk_fn),
                'DISK_FORMAT': 'ari',
                'CONTAINER_FORMAT': 'ari',
            }
        info['FILE_NAME'] = sh.joinpths(extract_dir, root_img_fn)
        info['DISK_FORMAT'] = 'ami'
        info['CONTAINER_FORMAT'] = 'ami'
        return info

    def unpack(self, file_name, file_location, tmp_dir):
        (_, fn_ext) = os.path.splitext(file_name)
        fn_ext = fn_ext.lower()
        if fn_ext in TAR_EXTS:
            return self._unpack_tar(file_name, file_location, tmp_dir)
        elif fn_ext in ['.img', '.qcow2']:
            info = dict()
            info['FILE_NAME'] = file_location
            if fn_ext == '.img':
                info['DISK_FORMAT'] = 'raw'
            else:
                info['DISK_FORMAT'] = 'qcow2'
            info['CONTAINER_FORMAT'] = 'bare'
            return info
        else:
            msg = "Currently we do not know how to unpack %r" % (file_name)
            raise IOError(msg)


class Registry(object):
    def __init__(self, cfg):
        self.cfg = cfg

    def _extract_names(self):
        names = dict()
        params = dict(self.cfg)
        cmd = {'cmd': IMAGE_LIST}
        res = utils.execute_template(cmd, params=params)
        if res:
            (stdout, _) = res[0]
            for line in stdout.splitlines():
                if line.startswith("|"):
                    pieces = line.split("|")
                    if len(pieces) >= 3:
                        name = pieces[2].strip()
                        image_id = pieces[1].strip()
                        if name and image_id:
                            names[name] = image_id
        return names

    def __contains__(self, name):
        names = self._extract_names()
        if name in names:
            return True
        else:
            return False


class Image(object):

    def __init__(self, url, cfg):
        self.url = url
        self.cfg = cfg
        self.registry = Registry(cfg)

    def _extract_id(self, output):
        if not output:
            return None
        for line in output.splitlines():
            if line.startswith("| id"):
                pieces = line.split("|")
                if len(pieces) >= 3:
                    return pieces[2].strip()
        return None

    def _check_name(self, name):
        LOG.info("Checking if image %s already exists already in glance.", colorizer.quote(name))
        if name in self.registry:
            raise IOError("Image named %s already exists." % (name))

    def _register(self, image_name, location):

        # Upload the kernel, if we have one
        kernel = location.pop('kernel', None)
        kernel_id = ''
        if kernel:
            params = dict(self.cfg)
            params.update(dict(kernel))
            kernel_image_name = "%s-vmlinuz" % (image_name)
            self._check_name(kernel_image_name)
            LOG.info('Adding kernel %s to glance.', colorizer.quote(kernel_image_name))
            params['NAME'] = kernel_image_name
            cmd = {'cmd': IMAGE_ADD}
            LOG.info("Please wait...")
            with open(params['FILE_NAME'], 'r') as fh:
                res = utils.execute_template(cmd,
                    params=params, stdin_fh=fh,
                    close_stdin=True)
            if res:
                (stdout, _) = res[0]
                kernel_id = self._extract_id(stdout)

        # Upload the ramdisk, if we have one
        initrd = location.pop('ramdisk', None)
        initrd_id = ''
        if initrd:
            params = dict(self.cfg)
            params.update(dict(initrd))
            ram_image_name = "%s-initrd" % (image_name)
            params['NAME'] = ram_image_name
            self._check_name(ram_image_name)
            LOG.info('Adding ramdisk %s to glance.', colorizer.quote(ram_image_name))
            cmd = {'cmd': IMAGE_ADD}
            LOG.info("Please wait...")
            with open(params['FILE_NAME'], 'r') as fh:
                res = utils.execute_template(cmd,
                    params=params, stdin_fh=fh,
                    close_stdin=True)
            if res:
                (stdout, _) = res[0]
                initrd_id = self._extract_id(stdout)

        # Upload the root, we must have one...
        root_image = dict(location)
        LOG.info('Adding image %s to glance.', colorizer.quote(image_name))
        add_cmd = list(IMAGE_ADD)
        params = dict(self.cfg)
        params.update(dict(root_image))
        self._check_name(image_name)
        params['NAME'] = image_name
        if kernel_id:
            add_cmd += ['--property', 'kernel_id=%KERNEL_ID%']
            params['KERNEL_ID'] = kernel_id
        if initrd_id:
            add_cmd += ['--property', 'ramdisk_id=%INITRD_ID%']
            params['INITRD_ID'] = initrd_id
        cmd = {'cmd': add_cmd}
        LOG.info("Please wait...")
        with open(params['FILE_NAME'], 'r') as fh:
            res = utils.execute_template(cmd,
                params=params, stdin_fh=fh,
                close_stdin=True)
        img_id = ''
        if res:
            (stdout, _) = res[0]
            img_id = self._extract_id(stdout)

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


class Service:
    def __init__(self, cfg):
        self.cfg = cfg

    def install(self, urls):
        # Install them in glance
        am_installed = 0
        if urls:
            utils.log_iterable(urls, logger=LOG,
                                header="Attempting to download+extract+upload %s images" % len(urls))
            for uri in urls:
                try:
                    (name, img_id) = Image(uri, self.cfg).install()
                    LOG.info("Installed image named %s with image id %s.", colorizer.quote(name), colorizer.quote(img_id))
                    am_installed += 1
                except (IOError, tarfile.TarError) as e:
                    LOG.exception('Installing %r failed due to: %s', uri, e)
        return am_installed
