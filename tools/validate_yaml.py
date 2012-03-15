#!/usr/bin/env python

"""Try to read a YAML file and report any errors.
"""

import sys

import yaml


with open(sys.argv[1], 'r') as f:
    yaml.load(f)
