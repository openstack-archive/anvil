import sys
import os
import tempfile

possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]), os.pardir, os.pardir))
sys.path.insert(0, possible_topdir)

from devstack import shell as sh
from devstack import settings
from devstack import utils

if __name__ == "__main__":
    ME = os.path.basename(sys.argv[0])
    if len(sys.argv) == 1:
        print("%s distro filename filename filename..." % (ME))
        sys.exit(0)
    distro = sys.argv[1]
    fns = sys.argv[2:len(sys.argv)]
    pips = dict()
    gen_type = "fedora.spec"
    for fn in fns:
        data = utils.load_json(fn)
        if distro in data:
            dpips = data.get(distro)
            for k in dpips.keys():
                data = dpips.get(k)
                version = data.get('version')
                if k in pips:
                    #check versions??
                    pass
                else:
                    pips[k] = version
    for (pip_name, version) in pips.items():
        print("Fetching %s (%s)" % (pip_name, version))
        cmd = ['py2pack'] + ['fetch', pip_name] + [version]
        (sysout, stderr) = sh.execute(*cmd)
        fn = pip_name + "-" + version + ".spec"
        cmd = ['py2pack'] + ['generate', '-t', gen_type, "-f", fn, pip_name] + [version]
        (sysout, stderr) = sh.execute(*cmd)
        print("Spec should be at %s" % (fn))


