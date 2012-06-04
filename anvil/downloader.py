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
import urllib2

import progressbar

from anvil import colorizer
from anvil import log as logging
from anvil import shell as sh

LOG = logging.getLogger(__name__)

# Git master branch
GIT_MASTER_BRANCH = "master"


class Downloader(object):

    def __init__(self, uri, store_where):
        self.uri = uri
        self.store_where = store_where

    def download(self):
        raise NotImplementedError()


class GitDownloader(Downloader):

    def __init__(self, distro, uri, store_where, branch):
        Downloader.__init__(self, uri, store_where)
        self.branch = branch
        self.distro = distro

    def download(self):
        dirsmade = list()
        if sh.isdir(self.store_where):
            LOG.info("Existing directory located at %s, leaving it alone.", colorizer.quote(self.store_where))
        else:
            LOG.info("Downloading %s to %s.", colorizer.quote(self.uri), colorizer.quote(self.store_where))
            dirsmade.extend(sh.mkdirslist(self.store_where))
            cmd = list(self.distro.get_command('git', 'clone'))
            cmd += [self.uri, self.store_where]
            sh.execute(*cmd)
        if self.branch and self.branch != GIT_MASTER_BRANCH:
            LOG.info("Adjusting branch to %s.", colorizer.quote(self.branch))
            cmd = list(self.distro.get_command('git', 'checkout'))
            cmd += [self.branch]
            sh.execute(*cmd, cwd=self.store_where)
        return dirsmade


class UrlLibDownloader(Downloader):

    def __init__(self, uri, store_where, **kargs):
        Downloader.__init__(self, uri, store_where)
        self.quiet = kargs.get('quiet', False)
        self.timeout = kargs.get('timeout', 5)

    def _make_bar(self, size):
        widgets = [
            'Fetching: ', progressbar.Percentage(),
            ' ', progressbar.Bar(),
            ' ', progressbar.ETA(),
            ' ', progressbar.FileTransferSpeed(),
        ]
        return progressbar.ProgressBar(widgets=widgets, maxval=size)

    def download(self):
        LOG.info('Downloading using urllib2: %s to %s.', colorizer.quote(self.uri), colorizer.quote(self.store_where))
        p_bar = None
        bytes_read = 0
        try:
            with contextlib.closing(urllib2.urlopen(self.uri, timeout=self.timeout)) as conn:
                with open(self.store_where, 'wb') as ofh:
                    c_len = conn.headers.get('content-length')
                    if c_len is not None:
                        try:
                            p_bar = self._make_bar(int(c_len))
                            p_bar.start()
                        except ValueError:
                            pass
                    while True:
                        data = conn.read(1024)
                        if data == '':
                            break
                        else:
                            ofh.write(data)
                            bytes_read += len(data)
                            if p_bar:
                                p_bar.update(bytes_read)
            return bytes_read
        finally:
            if p_bar:
                p_bar.finish()
