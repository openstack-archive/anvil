#!/usr/bin/env python

from distutils.version import LooseVersion

import os
import re
import sys
import yaml


if __name__ == '__main__':

    fn = sys.argv[1]
    with open(sys.argv[1], 'r') as fh:
        lines = fh.readlines()

    entries = set()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if re.match(r"\w(.*)", line):
            entries.add(line)

    versions = dict()
    split_on = set(['==', '>=', '<='])
    for entry in entries:
        matched = False
        for s in split_on:
            if entry.find(s) != -1:
                name, sep, version = entry.partition(s)
                if name and version.strip():
                    versions[name] = version.strip()
                    matched = True
                    break
        if not matched:
            versions[entry] = None

    cleaned_versions = dict()
    for (k, v) in versions.items():
        if not k:
            continue
        if not v or not v.strip():
            cleaned_versions[k] = None
        else:
            cleaned_versions[k] = LooseVersion(v)

    pips = []
    for (k, v) in cleaned_versions.items():
        if v:
            pips.append({
                'name': k,
                'version': str(v),
            })
        else:
            pips.append({'name': k})

    out = dict()
    out['pips'] = pips
    print(yaml.dump(out, default_flow_style=False, indent=4,
                line_break="\n", explicit_start=True, explicit_end=True))
