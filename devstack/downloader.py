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


from urlparse import urlparse
import re

from devstack import log as logging
from devstack import shell as sh
from devstack import env

LOG = logging.getLogger("devstack.downloader")
EXT_REG = re.compile(r"^(.*?)\.git\s*$", re.IGNORECASE)
GIT_MASTER_BRANCH = "master"
GIT_CACHE_DIR_ENV = "GIT_CACHE_DIR"


def _git_cache_download(storewhere, uri, branch=None):
    cdir = env.get_key(GIT_CACHE_DIR_ENV)
    if cdir and sh.isdir(cdir):
        #TODO actually do the cache...
        pass
    return False


def _gitdownload(storewhere, uri, branch=None):
    dirsmade = sh.mkdirslist(storewhere)
    LOG.info("Downloading from %s to %s" % (uri, storewhere))
    #check if already done
    if _git_cache_download(storewhere, uri, branch):
        return dirsmade
    #have to do it...
    cmd = ["git", "clone"] + [uri, storewhere]
    sh.execute(*cmd)
    if branch and branch != GIT_MASTER_BRANCH:
        LOG.info("Adjusting git branch to %s" % (branch))
        cmd = ['git', 'checkout'] + [branch]
        sh.execute(*cmd, cwd=storewhere)
    return dirsmade


def download(storewhere, uri, branch=None):
    #figure out which type
    up = urlparse(uri)
    if up and up.scheme.lower() == "git" or \
        EXT_REG.match(up.path):
        return _gitdownload(storewhere, uri, branch)
    else:
        msg = "Currently we do not know how to download from uri [%s]" % (uri)
        raise NotImplementedError(msg)
