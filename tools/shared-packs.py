import os
import sys
import yaml

import paste.util.multidict

possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))
if os.path.exists(os.path.join(possible_topdir,
                               'anvil',
                               '__init__.py')):
    sys.path.insert(0, possible_topdir)

from anvil import log
from anvil import utils


class CustomDumper(yaml.SafeDumper):
    def ignore_aliases(self, _data):
        return True


fn = sys.argv[1]
with open(fn, "r") as fh:
    data = fh.read()

b = yaml.load(data)

names = set()
for c in b['components']:
    names.add(c)


idf = 'packages'
pkgs = paste.util.multidict.MultiDict()
for name in names:
    data = b['components'][name]
    #print name
    for p in data.get(idf) or []:
        pname = p['name']
        pkgs.add(pname, p)

common = list()
for pkg in sorted(list(set(pkgs.keys()))):
    items = pkgs.getall(pkg)
    if len(items) > 1:
        print("Package dupe on: %r with %s dups" % (pkg, len(items)))
        versions = set()
        for v in items:
            if v.get('version'):
                versions.add(str(v.get('version')))
        if len(versions) > 1:
            print("\tWith many versions: %s" % (versions))
        else:
            print("\tAll with the same version %s" % (versions))
            common.append(items[0])

idf = 'pips'
pkgs = paste.util.multidict.MultiDict()
for name in names:
    data = b['components'][name]
    for p in data.get(idf) or []:
        pname = p['name']
        pkgs.add(pname, p)

print("-" * 20)
common_pips = list()
for pkg in sorted(list(set(pkgs.keys()))):
    items = pkgs.getall(pkg)
    if len(items) > 1:
        print("Pip dupe on: %r with %s dups" % (pkg, len(items)))
        versions = set()
        for v in items:
            if v.get('version'):
                versions.add(str(v.get('version')))
        if len(versions) > 1:
            print("\tWith many versions: %s" % (versions))
        else:
            print("\tAll with the same version %s" % (versions))
            common_pips.append(items[0])

#data = {'common': {'packages': common, 'pips': common_pips}}
#formatted =  yaml.dump(data,
#                    line_break="\n",
#                    indent=4,
#                    explicit_start=True,
#                    explicit_end=True,
#                    default_flow_style=False,
#                    Dumper=CustomDumper,
#                    )

#print formatted
