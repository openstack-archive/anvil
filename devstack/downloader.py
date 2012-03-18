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


import urllib

import progressbar

from devstack import log as logging
from devstack import shell as sh

LOG = logging.getLogger("devstack.downloader")

# Git commands/subcommands
GIT_MASTER_BRANCH = "master"
CLONE_CMD = ["git", "clone"]
CHECKOUT_CMD = ['git', 'checkout']
PULL_CMD = ['git', 'pull']


class Downloader(object):

    def __init__(self, uri, store_where):
        self.uri = uri
        self.store_where = store_where

    def download(self):
        raise NotImplementedError()


class GitDownloader(Downloader):

    def __init__(self, uri, store_where, **kargs):
        Downloader.__init__(self, uri, store_where)
        self.branch = kargs.get('branch')

    def download(self):
        dirsmade = list()
        if sh.isdir(self.store_where):
            LOG.info("Updating using git: located at %r" % (self.store_where))
            cmd = CHECKOUT_CMD + [GIT_MASTER_BRANCH]
            sh.execute(*cmd, cwd=self.store_where)
            cmd = PULL_CMD
            sh.execute(*cmd, cwd=self.store_where)
        else:
            LOG.info("Downloading using git: %r to %r" % (self.uri, self.store_where))
            dirsmade.extend(sh.mkdirslist(self.store_where))
            cmd = CLONE_CMD + [self.uri, self.store_where]
            sh.execute(*cmd)
        if self.branch and self.branch != GIT_MASTER_BRANCH:
            LOG.info("Adjusting branch using git: %r" % (self.branch))
            cmd = CHECKOUT_CMD + [self.branch]
            sh.execute(*cmd, cwd=self.store_where)
        return dirsmade


class UrlLibDownloader(Downloader):

    def __init__(self, uri, store_where, **kargs):
        Downloader.__init__(self, uri, store_where)
        self.quiet = kargs.get('quiet', False)
        self.p_bar = None

    def _make_bar(self, size):
        widgets = [
            'Fetching: ', progressbar.Percentage(),
            ' ', progressbar.Bar(),
            ' ', progressbar.ETA(),
            ' ', progressbar.FileTransferSpeed(),
        ]
        return progressbar.ProgressBar(widgets=widgets, maxval=size)

    def _report(self, blocks, block_size, total_size):
        if self.quiet:
            return
        byte_down = blocks * block_size
        if not self.p_bar:
            self.p_bar = self._make_bar(total_size)
            self.p_bar.start()
        if byte_down > self.p_bar.maxval:
            # This seems to happen, huh???
            pass
        else:
            self.p_bar.update(byte_down)

    def download(self):
        LOG.info('Downloading using urllib: %r to %r', self.uri, self.store_where)
        try:
            urllib.urlretrieve(self.uri, self.store_where, self._report)
        finally:
            if self.p_bar:
                self.p_bar.finish()
                self.p_bar = None
