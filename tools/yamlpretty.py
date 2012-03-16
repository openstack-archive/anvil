#!/usr/bin/env python

import yaml
import os
import sys

# See: http://pyyaml.org/wiki/PyYAMLDocumentation

if __name__ == "__main__":
    args = list(sys.argv)
    args = args[1:]
    for fn in args:
        data = None
        with open(fn, 'r') as fh:
            data = yaml.load(fh.read())
            fh.close()
        formatted = yaml.dump(data,
                            line_break="\n",
                            indent=4,
                            explicit_start=True,
                            explicit_end=True,
                            default_flow_style=False,
                            )
        print formatted
