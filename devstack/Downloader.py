from urlparse import urlparse
import re

from Shell import (execute, mkdirslist)
from Util import (create_regex, MASTER_BRANCH)
import Logger

LOG = Logger.getLogger("install.downloader")
EXT_REG = create_regex(r"/^(.*?)\.git\s*$/i")


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
