import os
import sys
import tempfile

possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]), os.pardir, os.pardir))
sys.path.insert(0, possible_topdir)

from devstack import utils
from devstack import settings
from devstack import component
from devstack.progs import common

def get_pips(c, distro):
    cls = common.get_action_cls(settings.INSTALL, c)
    dummy_config = common.get_config()
    dummy_root = tempfile.gettempdir()
    instance = cls(instances=set(), distro=distro,
                    packager=None, config=dummy_config,
                    root=dummy_root, opts=list(),
                    keep_old=False)
    if not isinstance(instance, component.PkgInstallComponent):
        return None
    else:
        return instance._get_pkgs_expanded()


if __name__ == "__main__":
    ME = os.path.basename(sys.argv[0])
    distro = sys.argv[1]
    for c in sorted(settings.COMPONENT_NAMES):
        print("Packages for %s:" % (utils.color_text(c, 'green')))
        pips = get_pips(c, distro)
        if pips is None or not pips:
            print("\t- %s" % (utils.color_text('N/A', 'red')))
        else:
            names = sorted(pips.keys())
            for name in names:
                real_name = name
                info = pips.get(name) or dict()
                if 'version' in info:
                    real_name = "%s (%s)" % (name, utils.color_text(str(info.get('version')), 'blue', bold=True))
                print("\t- %s" % real_name)
