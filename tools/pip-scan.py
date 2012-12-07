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
    requires_files = []
    for d in root_dirs:
        all_contents = sh.listdir(d, recursive=True, files_only=True)
        requires_files = [sh.abspth(f) for f in all_contents
                          if re.search("(test|pip)[-]requires", f, re.I)]
    requires_files = sorted(list(set(requires_files)))
    requirements = []
    for fn in requires_files:
        requirements.extend(pip_helper.parse_requirements(sh.load_file(fn)))
    requirements = set(requirements)
    yaml_fn = sh.abspth(sys.argv[1])
    distro_yaml = utils.load_yaml(yaml_fn)
    print("Comparing pips/pip2pkgs in %s to those found in %s" % (sys.argv[1], requires_files))
    components = distro_yaml.get('components', {})
    all_known_names = []
    for (_c, details) in components.items():
        pip2pkgs = details.get('pip_to_package', [])
        pips = details.get('pips', [])
        for item in pip2pkgs:
            all_known_names.append(item['name'].lower().strip())
        for item in pips:
            all_known_names.append(item['name'].lower().strip())
    all_known_names = sorted(list(set(all_known_names)))
    not_needed = []
    for n in all_known_names:
        if n not in requirements:
            not_needed.append(n)
    if not_needed:
        print("The following distro yaml mappings may not be needed:")
        for n in sorted(not_needed):
            print("  + %s" % (n))
    not_found = []
    for n in requirements:
        name = n.key.lower().strip()
        if name not in all_known_names:
            not_found.append(name)
    if not_found:
        print("The following distro yaml mappings may be required but where not found:")
        for n in sorted(not_found):
            print("  + %s" % (n))
    return len(not_found) + len(not_needed)


if __name__ == "__main__":
    sys.exit(main())
