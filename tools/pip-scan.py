#!/usr/bin/env python

import os
import sys
import re

possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))

if os.path.exists(os.path.join(possible_topdir,
                               'anvil',
                               '__init__.py')):
    sys.path.insert(0, possible_topdir)


from anvil import shell as sh
from anvil.packaging.helpers import pip_helper
from anvil import utils


def main():
    if len(sys.argv) < 3:
        print("%s distro_yaml root_dir ..." % sys.argv[0])
        return 1
    root_dirs = sys.argv[2:]
    yaml_fn = sh.abspth(sys.argv[1])

    requires_files = []
    for d in root_dirs:
        all_contents = sh.listdir(d, recursive=True, files_only=True)
        requires_files = [sh.abspth(f) for f in all_contents
                          if re.search(r"(test|pip)[-]requires$", f, re.I)]

    requires_files = sorted(list(set(requires_files)))
    requirements = []
    source_requirements = {}
    for fn in requires_files:
        source_requirements[fn] = []
        for req in pip_helper.parse_requirements(sh.load_file(fn)):
            requirements.append(req.key.lower().strip())
            source_requirements[fn].append(req.key.lower().strip())

    print(
        "Comparing pips/pip2pkgs in %s to those found in %s" %
        (yaml_fn, root_dirs))
    for fn in sorted(requires_files):
        print(" + " + str(fn))

    requirements = set(requirements)
    print("All known requirements:")
    for r in sorted(requirements):
        print("+ " + str(r))

    distro_yaml = utils.load_yaml(yaml_fn)
    components = distro_yaml.get('components', {})
    all_known_names = []
    components_pips = {}
    for (c, details) in components.items():
        components_pips[c] = []
        pip2pkgs = details.get('pip_to_package', [])
        pips = details.get('pips', [])
        known_names = []
        for item in pip2pkgs:
            known_names.append(item['name'].lower().strip())
        for item in pips:
            known_names.append(item['name'].lower().strip())
        components_pips[c].extend(known_names)
        all_known_names.extend(known_names)

    all_known_names = sorted(list(set(all_known_names)))
    not_needed = []
    for n in all_known_names:
        if n not in requirements:
            not_needed.append(n)
    if not_needed:
        print("The following distro yaml mappings may not be needed:")
        for n in sorted(not_needed):
            msg = "  + %s (" % (n)
            # Find which components said they need this...
            for (c, known_names) in components_pips.items():
                if n in known_names:
                    msg += c + ","
            msg += ")"
            print(msg)
    not_found = []
    for n in requirements:
        name = n.lower().strip()
        if name not in all_known_names:
            not_found.append(name)
    not_found = sorted(list(set(not_found)))
    if not_found:
        print(
            "The following distro yaml mappings may be required but were not found:")
        for n in sorted(not_found):
            msg = "  + %s" % (n)
            msg += " ("
            # Find which file/s said they need this...
            for (fn, reqs) in source_requirements.items():
                matched = False
                for r in reqs:
                    if r.lower().strip() == name:
                        matched = True
                if matched:
                    msg += fn + ","
            msg += ")"
            print(msg)
    return len(not_found) + len(not_needed)


if __name__ == "__main__":
    sys.exit(main())
