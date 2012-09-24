#!/usr/bin/env python

import os
import sys

import yaml

# See: http://pyyaml.org/wiki/PyYAMLDocumentation

if __name__ == "__main__":
    args = list(sys.argv)
    args = args[1:]
    for fn in args:
        fh = open(fn, 'r')
        data = yaml.load(fh.read())
        fh.close()
        formatted = yaml.dump(data,
                            line_break="\n",
                            indent=4,
                            explicit_start=True,
                            explicit_end=True,
                            default_flow_style=False,
                            )
        print("# Formatted %s" % (fn))
        print(formatted)