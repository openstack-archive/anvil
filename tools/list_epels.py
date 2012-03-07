import os
import sys
import tempfile

possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]), os.pardir, os.pardir))
sys.path.insert(0, possible_topdir)

from devstack import utils
from devstack import settings
from devstack import component
from devstack.progs import common

EPEL_DISTRO = settings.RHEL6

def get_epels(c, distro):
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
        pkgs = instance._get_pkgs_expanded()
        epel_pkgs = dict()
        for (name, info) in pkgs.items():
            meta = info.get("meta") or dict()
            if meta and meta.get("epel"):
                epel_pkgs[name] = info
        return epel_pkgs


if __name__ == "__main__":
    me = os.path.basename(sys.argv[0])
    distro = EPEL_DISTRO
    for c in sorted(settings.COMPONENT_NAMES):
        print("Packages for %s:" % (utils.color_text(c, 'green', bold=True, underline=True)))
        pkgs = get_epels(c, distro)
        if not pkgs:
            print("\t- %s" % (utils.color_text('N/A', 'red')))
        else:
            names = sorted(pkgs.keys())
            for name in names:
                real_name = name
                info = pkgs.get(name) or dict()
                if 'version' in info:
                    real_name = "%s (%s)" % (name, utils.color_text(str(info.get('version')), 'blue', bold=True))
                print("\t- %s" % real_name)
