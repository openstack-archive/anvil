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
import re
import urllib2

import progressbar

from anvil import colorizer
from anvil import exceptions
from anvil import log as logging
from anvil import shell as sh

LOG = logging.getLogger(__name__)

@six.add_metaclass(abc.ABCMeta)
class Downloader(object):

    def __init__(self, uri, dst):
        self._uri = uri
        self._dst = dst

    @abc.abstractmethod
    def download(self):
        raise NotImplementedError()


class GitDownloader(Downloader):

    def __init__(self, uri, dst, **kwargs):
        Downloader.__init__(self, uri, dst)
        self._branch = self._get_string_from_dict(kwargs, 'branch')
        self._tag = self._get_string_from_dict(kwargs, 'tag')
        self._sha1 = self._get_string_from_dict(kwargs, 'sha1')
        self._refspec = self._get_string_from_dict(kwargs, 'refspec')
        git_sources = len([a for a in (self._tag, self._sha1, self._branch) if a])
        if git_sources > 1:
            raise exceptions.ConfigException('Too many sources. Please, '
                                             'specify only one of tag/SHA1/branch.')
        if not git_sources:
            self._branch = 'master'

    def _get_string_from_dict(self, params, key):
        value = params.get(key)
        if value:
            value = str(value)
        return value

    def download(self):
        branch = self._branch
        tag = self._tag
        start_point = self._sha1 or self._tag
        if start_point:
            # Avoid 'detached HEAD state' message by moving to a
            # $tag-anvil branch for that tag
            new_branch = "%s-%s" % (start_point[:8], 'anvil')
            checkout_what = [start_point, '-b', new_branch]
        else:
            # Set it up to track the remote branch correctly
            new_branch = branch
            checkout_what = ['-t', '-b', new_branch, 'origin/%s' % branch]
        if sh.isdir(self._dst) and sh.isdir(sh.joinpths(self._dst, '.git')):
            LOG.info("Existing git directory located at %s, leaving it alone.",
                     colorizer.quote(self._dst))
            # do git clean -xdfq and git reset --hard to undo possible changes
            cmd = ["git", "clean", "-xdfq"]
            sh.execute(cmd, cwd=self._dst)
            cmd = ["git", "reset", "--hard"]
            sh.execute(cmd, cwd=self._dst)
            cmd = ["git", "fetch", "origin"]
            sh.execute(cmd, cwd=self._dst)
        else:
            LOG.info("Downloading %s to %s.", colorizer.quote(self._uri),
                     colorizer.quote(self._dst))
            cmd = ["git", "clone", self._uri, self._dst]
            sh.execute(cmd)
        if self._refspec:
            LOG.info("Fetching ref %s.", self._refspec)
            cmd = ["git", "fetch", self._uri, self._refspec]
            sh.execute(cmd, cwd=self._dst)
        if self._sha1:
            LOG.info("Adjusting to SHA1 %s.", colorizer.quote(self._sha1))
        elif tag:
            LOG.info("Adjusting to tag %s.", colorizer.quote(tag))
        else:
            LOG.info("Adjusting branch to %s.", colorizer.quote(branch))
        # detach, drop new_branch if it exists, and checkout to new_branch
        # newer git allows branch resetting: git checkout -B $new_branch
        # so, all these are for compatibility with older RHEL git
        cmd = ["git", "rev-parse", "HEAD"]
        git_head = sh.execute(cmd, cwd=self._dst)[0].strip()
        cmd = ["git", "checkout", git_head]
        sh.execute(cmd, cwd=self._dst)
        cmd = ["git", "branch", "-D", new_branch]
        sh.execute(cmd, cwd=self._dst, check_exit_code=False)
        cmd = ["git", "checkout"] + checkout_what
        sh.execute(cmd, cwd=self._dst)
        # NOTE(aababilov): old openstack.common.setup reports all tag that
        # contain HEAD as project's version. It breaks all RPM building
        # process, so, we will delete all extra tags
        cmd = ["git", "tag", "--contains", "HEAD"]
        tag_names = [
            i
            for i in sh.execute(cmd, cwd=self._dst)[0].splitlines()
            if i and i != tag]
        # Making sure we are not removing tag with the same commit reference
        # as for a branch. Otherwise this will make repository broken.
        if tag_names:
            cmd = ["git", "show-ref", "--tags", "--dereference"] + tag_names
            for line in sh.execute(cmd, cwd=self._dst)[0].splitlines():
                res = re.search(r"(.+)\s+refs/tags/(.+)\^\{\}$", line)
                if res is None:
                    continue
                ref, tag_name = res.groups()
                if ref == git_head and tag_name in tag_names:
                    tag_names.remove(tag_name)
        if tag_names:
            LOG.info("Removing tags: %s", colorizer.quote(" ".join(tag_names)))
            cmd = ["git", "tag", "-d"] + tag_names
            sh.execute(cmd, cwd=self._dst)


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
        LOG.info('Downloading using urllib2: %s to %s.',
                 colorizer.quote(self._uri), colorizer.quote(self._dst))
        p_bar = None

        def update_bar(progress_bar, bytes_down):
            if progress_bar:
                progress_bar.update(bytes_down)

        try:
            with contextlib.closing(urllib2.urlopen(self._uri, timeout=self.timeout)) as conn:
                c_len = conn.headers.get('content-length')
                if c_len is not None and not self.quiet:
                    try:
                        p_bar = self._make_bar(int(c_len))
                        p_bar.start()
                    except ValueError:
                        pass
                with open(self._dst, 'wb') as ofh:
                    return (self._dst, sh.pipe_in_out(conn, ofh,
                                                      chunk_cb=functools.partial(update_bar, p_bar)))
        finally:
            if p_bar:
                p_bar.finish()
