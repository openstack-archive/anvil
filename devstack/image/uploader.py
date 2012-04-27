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
import json
import os
import re
import tarfile
import urllib2
import urlparse

from devstack import downloader as down
from devstack import log
from devstack import shell as sh
from devstack import utils

from devstack.components import glance_client
from devstack.components import keystone

LOG = log.getLogger("devstack.image.uploader")

# Glance client commands
IMAGE_ADD = ['glance',
             '--os-auth-token', '%TOKEN%',
             '--os-image-url', '%GLANCE_HOSTPORT%',
             '--os-username', '%DEMO_USER_NAME%',
             '--os-tenant-name', '%DEMO_TENANT_NAME%',
             'image-create',
             '--name', '%NAME%',
             '--public',
             '--container-format', '%CONTAINER_FORMAT%',
             '--disk-format', '%DISK_FORMAT%']


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

        def is_kernel(fn):
            return re.match(r"(.*)-vmlinuz$", fn, re.I) or re.match(r'(.*?)aki-tty/image$', fn, re.I)

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
            raise RuntimeError(msg)
        extract_dir = sh.joinpths(tmp_dir, root_name)
        sh.mkdir(extract_dir)
        LOG.info("Extracting %r to %r", file_location, extract_dir)
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
            raise NotImplementedError(msg)


class Image(object):

    def __init__(self, url, token, cfg, pw_gen):
        self.url = url
        self.token = token
        self.cfg = cfg
        self.pw_gen = pw_gen

    def _extract_id(self, output):
        if not output:
            return None
        for line in output.splitlines():
            if line.startswith("| id"):
                return line.split("|")[2].strip()
        return None

    def _register(self, image_name, location):

        # Upload the kernel, if we have one
        kernel = location.pop('kernel', None)
        kernel_id = ''
        if kernel:
            LOG.info('Adding kernel %s to glance.', kernel)
            params = glance_client.get_shared_params(self.cfg)
            params.update(keystone.get_shared_params(self.cfg, self.pw_gen))
            params.update(dict(kernel))
            params['TOKEN'] = self.token
            params['NAME'] = "%s-vmlinuz" % (image_name)
            cmd = {'cmd': IMAGE_ADD}
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
            LOG.info('Adding ramdisk %s to glance.', initrd)
            params = glance_client.get_shared_params(self.cfg)
            params.update(keystone.get_shared_params(self.cfg, self.pw_gen))
            params.update(dict(initrd))
            params['TOKEN'] = self.token
            params['NAME'] = "%s-initrd" % (image_name)
            cmd = {'cmd': IMAGE_ADD}
            with open(params['FILE_NAME'], 'r') as fh:
                res = utils.execute_template(cmd,
                    params=params, stdin_fh=fh,
                    close_stdin=True)
            if res:
                (stdout, _) = res[0]
                initrd_id = self._extract_id(stdout)

        # Upload the root, we must have one...
        root_image = dict(location)
        LOG.info('Adding image %s to glance.', root_image)
        add_cmd = list(IMAGE_ADD)
        params = glance_client.get_shared_params(self.cfg)
        params.update(keystone.get_shared_params(self.cfg, self.pw_gen))
        params.update(dict(root_image))
        params['TOKEN'] = self.token
        params['NAME'] = image_name
        if kernel_id:
            add_cmd += ['--property', 'kernel_id=%KERNEL_ID%']
            params['KERNEL_ID'] = kernel_id
        if initrd_id:
            add_cmd += ['--property', 'ramdisk_id=%INITRD_ID%']
            params['INITRD_ID'] = initrd_id
        cmd = {'cmd': add_cmd}
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
            msg = "Can not determine file name from url: %r" % (self.url)
            raise RuntimeError(msg)
        with utils.tempdir() as tdir:
            fetch_fn = sh.joinpths(tdir, url_fn)
            down.UrlLibDownloader(self.url, fetch_fn).download()
            unpack_info = Unpacker().unpack(url_fn, fetch_fn, tdir)
            tgt_image_name = self._generate_img_name(url_fn)
            self._register(tgt_image_name, unpack_info)
            return tgt_image_name


class Service:
    def __init__(self, cfg, pw_gen):
        self.cfg = cfg
        self.pw_gen = pw_gen

    def _get_token(self):
        LOG.info("Fetching your keystone admin token so that we can perform image uploads/detail calls.")

        key_params = keystone.get_shared_params(self.cfg, self.pw_gen)
        keystone_service_url = key_params['SERVICE_ENDPOINT']
        keystone_token_url = "%s/tokens" % (keystone_service_url)

        # form the post json data
        data = json.dumps(
            {
                "auth":
                {
                    "passwordCredentials":
                    {
                        "username": key_params['ADMIN_USER_NAME'],
                        "password": key_params['ADMIN_PASSWORD'],
                    },
                    "tenantName": key_params['ADMIN_TENANT_NAME'],
                }
             })

        # Prepare the request
        headers = {
            'Content-Type': 'application/json'
        }
        request = urllib2.Request(keystone_token_url, data=data, headers=headers)

        # Make the request
        LOG.info("Getting your token from url %r, please wait..." % (keystone_token_url))
        LOG.debug("With post data %s" % (data))
        LOG.debug("With headers %s" % (headers))

        response = urllib2.urlopen(request)
        token = utils.get_from_path(json.loads(response.read()), "access/token/id")
        if not token:
            msg = "Response from url %r did not match expected json format." % (keystone_token_url)
            raise IOError(msg)

        LOG.debug("Got token %r" % (token))
        return token

    def install(self):
        LOG.info("Setting up any specified images in glance.")

        # Extract the urls from the config
        flat_locations = self.cfg.getdefaulted('img', 'image_urls', '')
        locations = [loc.strip() for loc in flat_locations.split(',') if len(loc.strip())]

        # Install them in glance
        am_installed = 0
        if locations:
            utils.log_iterable(locations, logger=LOG,
                                header="Attempting to download+extract+upload %s images" % len(locations))
            token = self._get_token()
            for uri in locations:
                try:
                    name = Image(uri, token, self.cfg, self.pw_gen).install()
                    if name:
                        LOG.info("Installed image named %r" % (name))
                        am_installed += 1
                except (IOError, tarfile.TarError) as e:
                    LOG.exception('Installing %r failed due to: %s', uri, e)
        return am_installed
