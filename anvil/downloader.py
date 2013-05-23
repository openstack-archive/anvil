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

import abc
import contextlib
import functools
import urllib2

from urlparse import parse_qs

import progressbar

from anvil import colorizer
from anvil import log as logging
from anvil import shell as sh

LOG = logging.getLogger(__name__)


class Downloader(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, uri, store_where):
        self.uri = uri
        self.store_where = store_where

    @abc.abstractmethod
    def download(self):
        raise NotImplementedError()


class GitDownloader(Downloader):
    def __init__(self, distro, uri, store_where):
        Downloader.__init__(self, uri, store_where)
        self.distro = distro

    def download(self):
        branch = None
        tag = None
        uri = self.uri
        if uri.find("?") != -1:
            # If we use urlparser here it doesn't seem to work right??
            # TODO(harlowja), why??
            (uri, params) = uri.split("?", 1)
            params = parse_qs(params)
            if 'branch' in params:
                branch = params['branch'][0].strip()
            if 'tag' in params:
                tag = params['tag'][0].strip()
            uri = uri.strip()
        if not branch:
            branch = 'master'
        if tag:
            # Avoid 'detached HEAD state' message by moving to a
            # $tag-anvil branch for that tag
            new_branch = "%s-%s" % (tag, 'anvil')
            checkout_what = [tag, '-b', new_branch]
        else:
            # Set it up to track the remote branch correctly
            new_branch = branch
            checkout_what = ['-t', '-b', new_branch, 'origin/%s' % branch]
        if sh.isdir(self.store_where) and sh.isdir(sh.joinpths(self.store_where, '.git')):
            LOG.info("Existing git directory located at %s, leaving it alone.", colorizer.quote(self.store_where))
            # do git clean -xdfq and git reset --hard to undo possible changes
            cmd = ["git", "clean", "-xdfq"]
            sh.execute(*cmd, cwd=self.store_where)
            cmd = ["git", "reset", "--hard"]
            sh.execute(*cmd, cwd=self.store_where)
            # detach, drop new_branch if it exists, and checkout to new_branch
            # newer git allows branch resetting: git checkout -B $new_branch
            # so, all these are for compatibility with older RHEL git
            cmd = ["git", "rev-parse", "HEAD"]
            git_head = sh.execute(*cmd, cwd=self.store_where)[0].strip()
            cmd = ["git", "checkout", git_head]
            sh.execute(*cmd, cwd=self.store_where)
            cmd = ["git", "branch", "-D", new_branch]
            sh.execute(*cmd, cwd=self.store_where, ignore_exit_code=True)
        else:
            LOG.info("Downloading %s (%s) to %s.", colorizer.quote(uri), branch, colorizer.quote(self.store_where))
            cmd = ["git", "clone", uri, self.store_where]
            sh.execute(*cmd)
        if tag:
            LOG.info("Adjusting to tag %s.", colorizer.quote(tag))
        else:
            LOG.info("Adjusting branch to %s.", colorizer.quote(branch))
        cmd = ["git", "checkout"] + checkout_what
        sh.execute(*cmd, cwd=self.store_where)


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

        def update_bar(progress_bar, bytes_down):
            if progress_bar:
                progress_bar.update(bytes_down)

        try:
            with contextlib.closing(urllib2.urlopen(self.uri, timeout=self.timeout)) as conn:
                c_len = conn.headers.get('content-length')
                if c_len is not None:
                    try:
                        p_bar = self._make_bar(int(c_len))
                        p_bar.start()
                    except ValueError:
                        pass
                with open(self.store_where, 'wb') as ofh:
                    return (self.store_where, sh.pipe_in_out(conn, ofh,
                                                             chunk_cb=functools.partial(update_bar, p_bar)))
        finally:
            if p_bar:
                p_bar.finish()
