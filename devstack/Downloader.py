# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

#TODO fix these
from Shell import (execute, mkdirslist)
from Util import (create_regex, MASTER_BRANCH)

import Logger

LOG = Logger.getLogger("install.downloader")
EXT_REG = re.compile(r"^(.*?)\.git\s*$", re.IGNORECASE)


def _gitdownload(storewhere, uri, branch=None):
    dirsmade = mkdirslist(storewhere)
    LOG.info("Downloading from %s to %s" % (uri, storewhere))
    cmd = ["git", "clone"] + [uri, storewhere]
    execute(*cmd)
    if(branch and branch != MASTER_BRANCH):
        LOG.info("Adjusting git branch to %s" % (branch))
        cmd = ['git', 'checkout'] + [branch]
        execute(*cmd, cwd=storewhere)
    return dirsmade


def download(storewhere, uri, branch=None):
    #figure out which type
    up = urlparse(uri)
    if(up and up.scheme.lower() == "git" or
        EXT_REG.match(up.path)):
        return _gitdownload(storewhere, uri, branch)
    else:
        msg = "Currently we do not know how to download %s" % (uri)
        raise NotImplementedError(msg)
