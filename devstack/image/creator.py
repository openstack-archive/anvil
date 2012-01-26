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

import os
import tarfile
import tempfile
import urllib
import ConfigParser

from devstack import log
from devstack import shell
from devstack import utils


LOG = log.getLogger("devstack.image.creator")


class Image(object):

    KERNEL_FORMAT = ['glance', '-A', '%TOKEN%', 'add', \
        'name="%IMAGE_NAME%-kernel"', 'is_public=true', 'container_format=aki', \
        'disk_format=aki']
    INITRD_FORMAT = ['glance', 'add', '-A', '%TOKEN%', \
        'name="%IMAGE_NAME%-ramdisk"', 'is_public=true', 'container_format=ari', \
        'disk_format=ari']
    IMAGE_FORMAT = ['glance', 'add', '-A', '%TOKEN%', 'name="%IMAGE_NAME%.img"', \
        'is_public=true', 'container_format=ami', 'disk_format=ami', \
        'kernel_id=%KERNEL_ID%', 'ramdisk_id=%INITRD_ID%']

    REPORTSIZE = 10485760

    tmpdir = tempfile.gettempdir()

    def __init__(self, url, token):
        self.url = url
        self.token = token
        self.download_name = url.split('/')[-1].lower()
        self.download_file_name = shell.joinpths(Image.tmpdir, self.download_name)
        self.image_name = None
        self.image = None
        self.kernel = None
        self.kernel_id = ''
        self.initrd = None
        self.initrd_id = ''
        self.tmp_folder = None
        self.registry = ImageRegistry(token)
        self.last_report = 0

    def _report(self, blocks, block_size, size):
        downloaded = blocks * block_size
        if downloaded - self.last_report > Image.REPORTSIZE:
            LOG.info('Downloading: %d/%d ', blocks * block_size, size)
            self.last_report = downloaded

    def _download(self):
        LOG.info('Downloading %s to %s', self.url, self.download_file_name)
        urllib.urlretrieve(self.url, self.download_file_name, self._report)

    def _unpack(self):
        parts = self.download_name.split('.')

        if self.download_name.endswith('.tgz') \
                or self.download_name.endswith('.tar.gz'):

            LOG.info('Extracting %s', self.download_file_name)
            self.image_name = self.download_name\
                .replace('.tgz', '').replace('.tar.gz', '')
            self.tmp_folder = shell.joinpths(Image.tmpdir, parts[0])
            shell.mkdir(self.tmp_folder)

            tar = tarfile.open(self.download_file_name)
            tar.extractall(self.tmp_folder)

            for file_ in shell.listdir(self.tmp_folder):
                if file_.find('vmlinuz') != -1:
                    self.kernel = shell.joinpths(self.tmp_folder, file_)
                elif file_.find('initrd') != -1:
                    self.initrd = shell.joinpths(self.tmp_folder, file_)
                elif file_.endswith('.img'):
                    self.image = shell.joinpths(self.tmp_folder, file_)
                else:
                    pass

        elif self.download_name.endswith('.img') \
                or self.download_name.endswith('.img.gz'):
            self.image_name = self.download_name.split('.img')[0]
            self.image = self.download_file_name

        else:
            raise IOError('Unknown image format for download %s' % (self.download_name))

    def _register(self):
        if self.kernel:
            LOG.info('Adding kernel %s to glance', self.kernel)
            params = {'TOKEN': self.token, 'IMAGE_NAME': self.image_name}
            cmd = {'cmd': Image.KERNEL_FORMAT}
            with open(self.kernel) as file_:
                res = utils.execute_template(cmd, params=params, stdin_fh=file_)
            self.kernel_id = res[0][0].split(':')[1].strip()

        if self.initrd:
            LOG.info('Adding ramdisk %s to glance', self.initrd)
            params = {'TOKEN': self.token, 'IMAGE_NAME': self.image_name}
            cmd = {'cmd': Image.INITRD_FORMAT}
            with open(self.initrd) as file_:
                res = utils.execute_template(cmd, params=params, stdin_fh=file_)
            self.initrd_id = res[0][0].split(':')[1].strip()

        LOG.info('Adding image %s to glance', self.image_name)
        params = {'TOKEN': self.token, 'IMAGE_NAME': self.image_name, \
                  'KERNEL_ID': self.kernel_id, 'INITRD_ID': self.initrd_id}
        cmd = {'cmd': Image.IMAGE_FORMAT}
        with open(self.image) as file_:
            utils.execute_template(cmd, params=params, stdin_fh=file_)

    def _cleanup(self):
        if self.tmp_folder:
            shell.deldir(self.tmp_folder)
        shell.unlink(self.download_file_name)

    def _generate_image_name(self, name):
        return name.replace('.tar.gz', '.img').replace('.tgz', '.img')\
            .replace('.img.gz', '.img')

    def install(self):
        possible_name = self._generate_image_name(self.download_name)
        if not self.registry.has_image(possible_name):
            try:
                self._download()
                self._unpack()
                if not self.registry.has_image(self.image_name + '.img'):
                    self._register()
            finally:
                self._cleanup()
        else:
            LOG.warn("You already seem to have image named %s, skipping" % (possible_name))


class ImageRegistry:

    CMD = ['glance', '-A', '%TOKEN%', 'details']

    def __init__(self, token):
        self._token = token
        self._info = {}
        self._load()

    def _parse(self, text):
        current = {}

        for line in text.split(os.linesep):
            if not line:
                continue

            if line.startswith("==="):
                if 'id' in current:
                    id_ = current['id']
                    del(current['id'])
                    self._info[id_] = current
                current = {}
            else:
                l = line.split(':', 1)
                current[l[0].strip().lower()] = l[1].strip().replace('"', '')

    def _load(self):
        LOG.info('Loading glance image information')
        params = {'TOKEN': self._token}
        cmd = {'cmd': ImageRegistry.CMD}
        res = utils.execute_template(cmd, params=params)
        self._parse(res[0][0])

    def has_image(self, image):
        return image in self.get_image_names()

    def get_image_names(self):
        return [self._info[k]['name'] for k in self._info.keys()]

    def __getitem__(self, id_):
        return self._info[id_]


class ImageCreationService:
    def __init__(self, cfg):
        self.cfg = cfg

    def install(self):
        urls = list()
        token = None

        #extract them
        try:
            token = self.cfg.get("passwords", "service_token")
            flat_urls = self.cfg.get('img', 'image_urls')
            if flat_urls:
                expanded_urls = [x.strip() for x in flat_urls.split(',')]
                for url in expanded_urls:
                    if url:
                        urls.append(url)
        except(ConfigParser.Error):
            LOG.info("No image configuration keys found, skipping glance image install")

        #install them in glance
        am_installed = 0
        if urls:
            LOG.info("Attempting to download & extract and upload (%s) images." % (", ".join(urls)))
            for url in urls:
                try:
                    Image(url, token).install()
                    am_installed += 1
                except (IOError, tarfile.TarError):
                    LOG.exception('Installing "%s" failed', url)
        return am_installed
