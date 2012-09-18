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
import functools
import urllib2

from urlparse import (urlparse, parse_qs)

import progressbar

from anvil import colorizer
from anvil import exceptions as excp
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

LOG = logging.getLogger(__name__)


class Downloader(object):
    def __init__(self, uri, store_where):
        self.uri = uri
        self.store_where = store_where

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
        if sh.isdir(self.store_where) and sh.isdir(sh.joinpths(self.store_where, '.git')):
            LOG.info("Existing git directory located at %s, leaving it alone.", colorizer.quote(self.store_where))
        else:
            LOG.info("Downloading %s (%s) to %s.", colorizer.quote(uri), branch, colorizer.quote(self.store_where))
            cmd = list(self.distro.get_command('git', 'clone'))
            cmd += [uri, self.store_where]
            sh.execute(*cmd)
        if branch or tag:
            checkout_what = []
            if tag:
                # Avoid 'detached HEAD state' message by moving to a 
                # $tag-anvil branch for that tag
                checkout_what = [tag, '-b', "%s-%s" % (tag, 'anvil')]
                LOG.info("Adjusting to tag %s.", colorizer.quote(tag))
            else:
                if branch.lower() == 'master':
                    checkout_what = ['master']
                else:
                    # Set it up to track the remote branch correctly
                    checkout_what = ['--track', '-b', branch, 'origin/%s' % (branch)]
                LOG.info("Adjusting branch to %s.", colorizer.quote(branch))
            cmd = list(self.distro.get_command('git', 'checkout'))
            cmd += checkout_what
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


def download(distro, uri, target_dir, **kwargs):
    puri = urlparse(uri)
    scheme = puri.scheme.lower()
    path = puri.path.strip().split("?", 1)[0]
    if scheme == 'git' or path.lower().endswith('.git'):
        downloader = GitDownloader(distro, uri, target_dir)
        downloader.download()
    elif scheme in ['http', 'https']:
        with utils.tempdir() as tdir:
            fn = sh.basename(path)
            downloader = UrlLibDownloader(uri, sh.joinpths(tdir, fn))
            downloader.download()
            if fn.endswith('.tar.gz'):
                cmd = ['tar', '-xzvf', sh.joinpths(tdir, fn), '-C', target_dir]
                sh.execute(*cmd)
            elif fn.endswith('.zip'):
                # TODO(harlowja) this might not be 100% right...
                # we might have to move the finished directory...
                cmd = ['unzip', sh.joinpths(tdir, fn), '-d', target_dir]
                sh.execute(*cmd)
            else:
                raise excp.DownloadException("Unable to extract %s downloaded from %s" % (fn, uri))
    else:
        raise excp.DownloadException("Unknown scheme %s, unable to download from %s" % (scheme, uri))
