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

LOG = logging.getLogger("devstack.downloader")
EXT_REG = re.compile(r"^(.*?)\.git\s*$", re.IGNORECASE)
GIT_MASTER_BRANCH = "master"
CLONE_CMD = ["git", "clone"]
CHECKOUT_CMD = ['git', 'checkout']
PULL_CMD = ['git', 'pull']


def _gitdownload(storewhere, uri, branch=None):
    dirsmade = list()
    if sh.isdir(storewhere):
        LOG.info("Updating code located at [%s]" % (storewhere))
        cmd = CHECKOUT_CMD + [GIT_MASTER_BRANCH]
        sh.execute(*cmd, cwd=storewhere)
        cmd = PULL_CMD
        sh.execute(*cmd, cwd=storewhere)
    else:
        LOG.info("Downloading from [%s] to [%s]" % (uri, storewhere))
        dirsmade.extend(sh.mkdirslist(storewhere))
        cmd = CLONE_CMD + [uri, storewhere]
        sh.execute(*cmd)
    if branch and branch != GIT_MASTER_BRANCH:
        LOG.info("Adjusting git branch to [%s]" % (branch))
        cmd = CHECKOUT_CMD + [branch]
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
