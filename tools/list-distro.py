#!/usr/bin/env python

import distutils.version
import os
import sys
import tempfile

from termcolor import cprint, colored
import yaml

def find_all(mp, key, accum):
    if type(mp) is dict:
        if key in mp:
            value = mp[key]
            if type(value) is list:
                for v in value:
                    accum.append(v)
        else:
            for (k, v) in mp.items():
                find_all(v, key, accum)


def print_versions(items):
    names = set([p['name'] for p in items])
    for n in sorted(names):
        versions_found = list()
        for p in items:
            if p['name'] == n:
                version = p.get('version')
                if version:
                    version = str(version)
                    version = version.replace("*", "0")
                    versions_found.append(distutils.version.LooseVersion(version))
        highest_version = "??"
        if versions_found:
            versions_found.sort()
            highest_version = "%s" % (versions_found[-1])
        print("|")
        print("|--%s (%s)" % (colored(n, 'blue'), colored(highest_version, 'yellow')))
        metas = dict()
        for p in items:
            if p['name'] == n:
                meta = p.get('meta')
                if meta:
                    for (k, v) in meta.items():
                        metas[k] = v
        if metas:
            for (k, v) in metas.items():
                print("|")
                print("|---- %s => %s" % (colored(k, 'blue'), colored(str(v), 'yellow')))


if __name__ == "__main__":
    me = os.path.basename(sys.argv[0])
    if len(sys.argv) < 2:
        print("%s distro" % (me))
        sys.exit(1)

    distro_fn = sys.argv[1]
    data = None
    with open(distro_fn, 'r') as fh:
        data = yaml.load(fh.read())
    pips = list()
    find_all(data, 'pips', pips)
    pkgs = list()
    find_all(data, 'packages', pkgs)
    cprint("<PIPS>", 'green')
    print_versions(pips)
    print("")
    cprint("<PKGS>", 'green')
    print_versions(pkgs)
    
